from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class HelpdeskTicketTeamTransferWizard(models.TransientModel):
    _name = "helpdesk.ticket.team.transfer.wizard"
    _description = "Transfer Helpdesk Ticket To Another Team"

    ticket_id = fields.Many2one("helpdesk.ticket", string="Ticket", required=True, readonly=True)
    current_team_id = fields.Many2one(
        "helpdesk.team",
        string="Current Team",
        related="ticket_id.team_id",
        readonly=True,
    )
    team_id = fields.Many2one("helpdesk.team", string="New Team", required=True)
    manager_id = fields.Many2one(
        "res.users",
        string="New Team Manager",
        related="team_id.team_manager_id",
        readonly=True,
    )

    def action_transfer(self):
        self.ensure_one()
        ticket = self.ticket_id.exists()
        new_team = self.team_id.exists()

        if not ticket:
            raise UserError(_("The selected ticket no longer exists."))
        if not new_team:
            raise UserError(_("Please select a valid Helpdesk Team."))
        new_team.check_access_rights("read")
        new_team.check_access_rule("read")
        if ticket.team_id == new_team:
            raise UserError(_("Please select a different Helpdesk Team."))
        if not new_team.team_manager_id:
            raise UserError(_("The selected Helpdesk Team must have a Team Manager before transfer."))

        try:
            ticket.check_access_rights("write")
            ticket.check_access_rule("write")
        except AccessError:
            raise AccessError(_("You do not have permission to transfer this ticket."))

        old_team_name = ticket.team_id.display_name or _("No Team")
        new_team_name = new_team.display_name
        manager_name = new_team.team_manager_id.display_name

        ticket.write(
            {
                "team_id": new_team.id,
                "user_id": new_team.team_manager_id.id,
            }
        )
        ticket.sudo().message_post(
            body=_(
                "Ticket transferred from %(old_team)s to %(new_team)s and assigned to %(manager)s.",
                old_team=old_team_name,
                new_team=new_team_name,
                manager=manager_name,
            ),
            subtype_xmlid="mail.mt_note",
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Ticket Transferred"),
                "message": _("Ticket transferred to %s and assigned to %s.") % (new_team_name, manager_name),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
