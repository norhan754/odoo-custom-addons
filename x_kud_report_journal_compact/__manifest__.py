# -*- coding: utf-8 -*-
{
    "name": "KUD Reports - Compact Journals Filter",
    "version": "17.0.3.0.0",
    "summary": "Show Journal Groups only in the Journals filter, plus a one-click Select all",
    "description": """
KUD Reports - Compact Journals Filter
=====================================

The Journals dropdown of the accounting reports lists every journal of every
open company. For KUD that is 36 journals for the holding alone, so the list
that matters - the four Journal Groups - is buried under a scrollbar.

This collapses the individual journals behind a "Show individual journals"
row, so the dropdown opens on the groups, and adds a "Select all journals"
entry next to the existing "Unselect all journals" one.

WHY IT CANNOT CHANGE THE FIGURES
--------------------------------
account_reports builds the report domain from the SAME list it renders:

    def _get_options_journals_domain(self, options):
        selected_journals = self._get_options_journals(options)
        return selected_journals and [('journal_id', 'in', [j['id'] for j in selected_journals])] or []

So anything dropped from `options['journals']` is also dropped from the
report. This module therefore never touches `options`: it only swaps the list
the TEMPLATE iterates over (`t-foreach`) for a filtered copy. The options dict
the server receives is byte for byte the one stock Odoo would have sent, and
every figure is unchanged.

For the same reason archiving journals is not an option either - see
_get_filter_journals, which searches with active_test=False, so archived
journals stay in the list anyway.

Frontend only: an OWL template extension plus a patch on
AccountReportFilters.prototype. No Python, no model, no data.
""",
    "author": "KUD",
    "license": "LGPL-3",
    "category": "Accounting",
    "depends": ["account_reports"],
    "assets": {
        "web.assets_backend": [
            "x_kud_report_journal_compact/static/src/js/journal_compact.js",
            "x_kud_report_journal_compact/static/src/xml/journal_compact.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
