from odoo import _, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    def action_open_transfer_team_wizard(self):
        self.ensure_one()
        self.check_access_rights("write")
        self.check_access_rule("write")

        return {
            "type": "ir.actions.act_window",
            "name": _("Transfer To Another Team"),
            "res_model": "helpdesk.ticket.team.transfer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_ticket_id": self.id,
                "default_current_team_id": self.team_id.id,
            },
        }
