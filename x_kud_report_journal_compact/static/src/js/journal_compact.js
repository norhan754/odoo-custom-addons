/** @odoo-module **/

import { onWillRender, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { AccountReportController } from "@account_reports/components/account_report/controller";

/**
 * Compacts the Journals dropdown of the accounting reports.
 *
 * `controller.options.journals` is a flat list mixing four kinds of rows:
 *   - {id: 'divider', model: 'account.journal.group'}  -> the "Journal Groups" header
 *   - {id: <int>,     model: 'account.journal.group'}  -> a group
 *   - {id: 'divider', model: 'res.company'}            -> a company header
 *   - {id: <int>,     model: 'account.journal'}        -> a journal
 *
 * We hide the last two kinds from the RENDER only. `options` itself is never
 * modified, which is what keeps the report's figures identical: the server
 * rebuilds the journal domain from `options['journals']`, not from what the
 * dropdown happened to draw.
 */
patch(AccountReportFilters.prototype, {
    setup() {
        super.setup();
        // Collapsed on open; the choice lives as long as the report component does.
        this.kudJournalUI = useState({ expanded: false, groupCompany: {} });
        // Group ids already sent to the server, so a failed read is not retried
        // on every render.
        this.kudCompanyReadIssued = new Set();
        onWillRender(() => this.kudLoadGroupCompanies());
    },

    get kudJournalRows() {
        return this.controller.options.journals || [];
    },

    get kudGroupRows() {
        return this.kudJournalRows.filter(
            (row) => row.model === "account.journal.group" && row.id !== "divider"
        );
    },

    get kudShowIndividualJournals() {
        return this.kudJournalUI.expanded;
    },

    /** Number of individual journals currently collapsed away. */
    get kudIndividualJournalCount() {
        return this.kudJournalRows.filter((row) => row.model === "account.journal").length;
    },

    /** The rows the template actually draws. A view of options, never a replacement. */
    get kudVisibleJournalRows() {
        if (this.kudShowIndividualJournals) {
            return this.kudJournalRows;
        }
        return this.kudJournalRows.filter(
            (row) =>
                row.model !== "account.journal" &&
                // drop the now-empty per-company headers as well
                !(row.id === "divider" && row.model === "res.company")
        );
    },

    kudToggleIndividualJournals() {
        this.kudJournalUI.expanded = !this.kudJournalUI.expanded;
    },

    //--------------------------------------------------------------------------
    // Telling apart same-named groups of different companies
    //--------------------------------------------------------------------------

    get kudMultiCompany() {
        return (this.controller.options.companies || []).length > 1;
    },

    /**
     * Odoo puts every company's groups under one "Journal Groups" header and
     * gives the rows no company of their own - only the journals below them
     * carry company headers, and we just collapsed those. With all companies
     * open that leaves eight indistinguishable "Cash" rows, so read the owning
     * company once per group and show it.
     *
     * A plain read through the standard ORM route: no server-side code of ours
     * runs, and nothing here reaches the report's options.
     */
    kudLoadGroupCompanies() {
        if (!this.kudMultiCompany) {
            return;
        }
        const missing = this.kudGroupRows
            .map((row) => row.id)
            .filter((id) => !this.kudCompanyReadIssued.has(id));
        if (!missing.length) {
            return;
        }
        missing.forEach((id) => this.kudCompanyReadIssued.add(id));
        this.controller.orm
            .read("account.journal.group", missing, ["company_id"])
            .then((records) => {
                for (const record of records) {
                    this.kudJournalUI.groupCompany[record.id] = record.company_id
                        ? record.company_id[1]
                        : "";
                }
            })
            .catch(() => {
                // Labels stay bare. Nothing else depends on this.
            });
    },

    kudRowLabel(row) {
        if (row.model !== "account.journal.group" || !this.kudMultiCompany) {
            return row.name;
        }
        const company = this.kudJournalUI.groupCompany[row.id];
        return company ? `${row.name} — ${company}` : row.name;
    },

    //--------------------------------------------------------------------------
    // Bulk selection
    //--------------------------------------------------------------------------

    get kudAnyJournalSelected() {
        return this.kudJournalRows.some((row) => row.selected);
    },

    /**
     * kud_report_journal_clear ships the very same entry. It is installed on
     * staging but not on production, so render ours only when it is absent -
     * one "Unselect all journals" either way.
     */
    get kudShowUnselectAll() {
        return this.kudAnyJournalSelected && !("kudClearJournals" in this);
    },

    /**
     * Ticks every journal in one click.
     *
     * The server normalises "every journal selected" back to "All Journals"
     * (see _init_options_journals: when selected_journals == available_journals
     * for every company it empties names_to_display and unticks the rows). That
     * is the same end state, and the same domain - an unfiltered report.
     */
    async kudSelectAllJournals() {
        for (const row of this.kudJournalRows) {
            if (row.model === "account.journal") {
                row.selected = true;
            } else if (row.model === "account.journal.group") {
                row.selected = false;
            }
        }
        await this.kudReloadJournals();
    },

    /** Clears the filter, which the server reads as "All Journals". */
    async kudUnselectAllJournals() {
        for (const row of this.kudJournalRows) {
            row.selected = false;
        }
        await this.kudReloadJournals();
    },

    async kudReloadJournals() {
        // `__journal_group_action` is a one-shot instruction telling the server
        // to add or remove a single group. A stale one would be re-applied
        // right after we changed the selection ourselves.
        delete this.controller.options.__journal_group_action;

        await this.controller.reload("journals", this.controller.options);
    },
});

//------------------------------------------------------------------------------
// Every report opens on All Journals
//------------------------------------------------------------------------------

/**
 * Report actions already started on All Journals, by action jsId. A menu click
 * or a doAction mints a fresh jsId; a breadcrumb back to the same report reuses
 * it, so a filter picked during the visit survives the round trip.
 */
const kudJournalResetDone = new Set();

/**
 * Stock Odoo opens a report on a journal filter nobody chose:
 *   - first visit: _init_options_journals ticks the first journal group by
 *     sequence. Every group here has sequence 10, so which one wins is down to
 *     row order in PostgreSQL - it was Checks & Notes on the day we looked.
 *   - later visits: the last filter comes back from sessionStorage.
 * Either way a partner ledger can open silently missing whole journals. One
 * did: a customer read 0.00 against a true -7,200,000 because CASH4 was out.
 *
 * An empty `journals` list in the options sent to get_options makes the server
 * take its "reload previous" branch with nothing selected, which it reports as
 * All Journals. Measured on production across Partner Ledger, Trial Balance,
 * Balance Sheet, General Ledger and P&L: no other option changes.
 */
patch(AccountReportController.prototype, {
    async load(env) {
        const jsId = this.action.jsId;
        if (!jsId || !kudJournalResetDone.has(jsId)) {
            if (jsId) {
                kudJournalResetDone.add(jsId);
            }
            this.kudStartOnAllJournals();
        }
        return super.load(env);
    },

    kudStartOnAllJournals() {
        // sessionOptionsID() reads this, and super.load() only sets it after
        // we run. Same value, one line early.
        this.actionReportId = this.action.context.report_id;

        const params = this.action.params || {};
        if (params.ignore_session || !this.hasSessionOptions()) {
            const options = params.options || {};
            // A drill-down from another report that carries a journal filter
            // keeps it: that is the view the user clicked through to.
            if ((options.journals || []).some((journal) => journal.selected)) {
                return;
            }
            this.action.params = { ...params, options: { ...options, journals: [] } };
        } else {
            const options = this.sessionOptions();
            options.journals = [];
            delete options.__journal_group_action;
            this.saveSessionOptions(options);
        }
    },
});
