
# KUD AUTOREC — الحارس: يفحص سلامة النظام ويوقفه تلقائياً عند أي خطر، ويبلّغ.
# v2: التوقف كان صامتاً — يقلب kud_autorec.mode إلى off ويكتب السبب في الإعدادات
# والسجل فقط، فقد تتوقف التسوية أسابيع دون أن يعلم أحد. الآن يُبلغ قناة AUTOPILOT
# (kud_fn.channel_id) ويفتح مهمة To-Do لكل مستخدم في kud_autorec.alert_user_ids.
# وإن تعطّل الحارس نفسه أبلغ مرة واحدة يومياً بدل أن يفشل صامتاً.
ICP = env['ir.config_parameter'].sudo()
problems = []
crash = ''
n24 = 0
v24 = 0.0

# الفحوص داخل savepoint: لو فشل استعلام، لا تُترك المعاملة مُجهَضة فيضيع التبليغ معها.
env.flush_all()
env.cr.execute('SAVEPOINT kud_guard_checks')
try:
    # 1) أي فاتورة مورد برصيد سالب = تخصيص زائد
    env.cr.execute("SELECT COUNT(*) FROM account_move WHERE move_type IN ('in_invoice','in_receipt') AND state='posted' AND amount_residual < -0.01")
    neg_bills = int(env.cr.fetchone()[0])
    if neg_bills > 0:
        problems.append(u'%s فاتورة برصيد سالب (تخصيص زائد)' % neg_bills)
    # 2) أي سطر مدين على حساب الدائنين برصيد سالب
    env.cr.execute("SELECT COUNT(*) FROM account_move_line l JOIN account_account a ON a.id=l.account_id WHERE a.account_type='liability_payable' AND l.debit>0 AND l.amount_residual < -0.01")
    neg_lines = int(env.cr.fetchone()[0])
    if neg_lines > 0:
        problems.append(u'%s سطر سداد برصيد سالب' % neg_lines)
    # 3) توازن المدين والدائن لكل شركة
    env.cr.execute("SELECT company_id, COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line GROUP BY company_id")
    for r in env.cr.fetchall():
        if abs(float(r[1]) - float(r[2])) > 0.01:
            problems.append(u'شركة %s: المدين لا يساوي الدائن (فرق %.2f)' % (r[0], float(r[1]) - float(r[2])))
    # 4) حصاد آخر 24 ساعة
    env.cr.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM account_partial_reconcile WHERE create_date > (now() - interval '24 hours')")
    d = env.cr.fetchone()
    n24 = int(d[0])
    v24 = float(d[1])
    # 5) معدل غير طبيعي؟
    CAPDAY = int(ICP.get_param('kud_autorec.guard_max_per_day') or 1500)
    if n24 > CAPDAY:
        problems.append(u'عدد تسويات غير طبيعي في 24 ساعة: %s (الحد %s)' % (n24, CAPDAY))
    env.cr.execute('RELEASE SAVEPOINT kud_guard_checks')
except Exception as e:
    env.clear()
    env.cr.execute('ROLLBACK TO SAVEPOINT kud_guard_checks')
    crash = str(e)[:300]

mode = (ICP.get_param('kud_autorec.mode', 'off') or 'off').strip()
now = str(datetime.datetime.now())[:19]
status = u'سليم'
alert_kind = ''
if crash:
    # الحارس لا يستطيع الفحص. لا نوقف التسوية بسبب عطل في الحارس نفسه —
    # التسوية لا تُخصِّص أكثر من الرصيد بطبيعتها — لكن نُبلغ، مرة واحدة يومياً.
    status = u'عطل في الحارس'
    today = str(datetime.date.today())
    if ICP.get_param('kud_autorec.guard_crash_alerted_on') != today:
        ICP.set_param('kud_autorec.guard_crash_alerted_on', today)
        alert_kind = 'crash'
elif problems:
    status = u'خطر'
    if mode != 'off':
        ICP.set_param('kud_autorec.mode', 'off')
        ICP.set_param('kud_autorec.tripped_at', str(datetime.datetime.now()))
        ICP.set_param('kud_autorec.tripped_reason', u' | '.join(problems)[:500])
        # يُبلَّغ مرة عند لحظة الإيقاف فقط؛ الفحوص التالية تجد mode = off فلا تكرّر.
        alert_kind = 'trip'

findings = u' | '.join(problems) or (crash and (u'تعذّر الفحص: ' + crash)) or u'لا مشاكل'
ICP.set_param('kud_autorec.guard_last_run', str(datetime.datetime.now()))
ICP.set_param('kud_autorec.guard_status', status)
ICP.set_param('kud_autorec.guard_24h_count', str(n24))
ICP.set_param('kud_autorec.guard_24h_value', str(round(v24, 2)))
ICP.set_param('kud_autorec.guard_findings', findings[:500])
env['ir.logging'].sudo().create({
    'name': 'KUD AUTOREC GUARD', 'type': 'server', 'dbname': env.cr.dbname,
    'level': 'ERROR' if (problems or crash) else 'INFO', 'path': 'kud_autorec.guard',
    'func': 'guard', 'line': '0',
    'message': u'الحالة: %s | تسويات 24س: %s بقيمة %.2f | %s' % (status, n24, v24, findings),
})

# التبليغ في savepoint مستقل: لو فشل (قناة محذوفة، مستخدم معطّل...) لا يجوز أن
# يُلغي الإيقاف الذي حدث للتو. يُسجَّل الفشل ويستمر.
if alert_kind:
    # set_param وir.logging أعلاه مُخزَّنة في ذاكرة الـORM لم تُكتب بعد. بدون flush هنا
    # تُكتب داخل savepoint التبليغ، فلو فشل التبليغ ورجع الـsavepoint رجع معه
    # الإيقاف نفسه — وهذا ما أظهره الاختبار. الـflush يثبّت الإيقاف قبل التبليغ.
    env.flush_all()
    env.cr.execute('SAVEPOINT kud_guard_alert')
    try:
        bot_pid = int(ICP.get_param('kud_fn.bot_partner_id') or 0) or None
        ch_id = int(ICP.get_param('kud_fn.channel_id') or 0)
        detail = (findings or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if alert_kind == 'trip':
            summary = u'التسوية التلقائية متوقفة — راجع تنبيه الحارس'
            body = (u'<p>&#128721; <b>التسوية التلقائية لفواتير الموردين اتوقفت تلقائياً</b></p>'
                    u'<p><b>السبب:</b> %s</p>'
                    u'<p><b>الوقت:</b> %s</p>'
                    u'<p>الحارس لقى المشكلة دي فحوّل <code>kud_autorec.mode</code> إلى <code>off</code>. '
                    u'مفيش أي تسوية تلقائية هتحصل لحد ما حد يراجع.</p>'
                    u'<p><b>المطلوب:</b> مراجعة السبب، وبعدها إعادة التشغيل من '
                    u'Settings &#8250; Technical &#8250; System Parameters &#8250; '
                    u'<code>kud_autorec.mode</code> = <code>on</code>.</p>') % (detail, now)
        else:
            summary = u'حارس التسوية التلقائية فيه عطل'
            body = (u'<p>&#9888;&#65039; <b>حارس التسوية التلقائية نفسه فيه عطل</b></p>'
                    u'<p><b>الخطأ:</b> %s</p>'
                    u'<p><b>الوقت:</b> %s</p>'
                    u'<p>التسوية التلقائية لسه شغالة، لكن من غير رقابة لحد ما العطل يتصلّح. '
                    u'التنبيه ده بيتبعت مرة واحدة في اليوم.</p>') % (detail, now)
        if ch_id:
            ch = env['discuss.channel'].sudo().browse(ch_id)
            m = ch.message_post(author_id=bot_pid, body='...', message_type='comment', subtype_xmlid='mail.mt_comment')
            m.sudo().write({'body': body})
        uids = []
        for x in (ICP.get_param('kud_autorec.alert_user_ids') or '').split(','):
            if x.strip().isdigit():
                uids.append(int(x.strip()))
        if uids and bot_pid:
            holder = env['res.partner'].sudo().browse(bot_pid)
            for uid_ in uids:
                holder.activity_schedule('mail.mail_activity_data_todo', user_id=uid_,
                                         summary=summary, note=body)
        env.cr.execute('RELEASE SAVEPOINT kud_guard_alert')
    except Exception as e:
        # env.clear() أولاً: وإلا تُكتب كتابات التبليغ الفاشل المعلّقة لاحقاً خارج الـsavepoint.
        env.clear()
        env.cr.execute('ROLLBACK TO SAVEPOINT kud_guard_alert')
        env['ir.logging'].sudo().create({
            'name': 'KUD AUTOREC GUARD', 'type': 'server', 'dbname': env.cr.dbname,
            'level': 'ERROR', 'path': 'kud_autorec.guard', 'func': 'alert', 'line': '0',
            'message': u'فشل إرسال تنبيه الحارس (%s): %s' % (alert_kind, str(e)[:300]),
        })
