from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    team_manager_id = fields.Many2one(
        "res.users",
        string="Team Manager",
        domain=[("share", "=", False)],
        help="Internal user who can access and manage all tickets assigned to this Helpdesk Team.",
    )

    def _check_team_manager_edit_access(self, vals):
        if "team_manager_id" in vals and not self.env.user.has_group("helpdesk.group_helpdesk_manager"):
            raise AccessError(_("Only Helpdesk administrators can edit the Team Manager."))
        if vals.get("team_manager_id"):
            manager = self.env["res.users"].browse(vals["team_manager_id"])
            if manager.exists() and manager.share:
                raise ValidationError(_("The Team Manager must be an internal user."))

    def _sync_team_manager_security_group(self):
        group = self.env.ref(
            "helpdesk_team_manager_access.group_helpdesk_team_manager",
            raise_if_not_found=False,
        )
        if not group:
            return

        managers = self.search([("team_manager_id", "!=", False)]).mapped("team_manager_id").filtered(
            lambda user: user and not user.share
        )
        for manager in managers:
            if group not in manager.groups_id:
                manager.sudo().write({"groups_id": [(4, group.id)]})

        stale_managers = group.users - managers
        if stale_managers:
            stale_managers.sudo().write({"groups_id": [(3, group.id)]})

    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            self._check_team_manager_edit_access(vals)
        teams = super().create(vals_list)
        teams._sync_team_manager_security_group()
        return teams

    def write(self, vals):
        self._check_team_manager_edit_access(vals)
        result = super().write(vals)
        if "team_manager_id" in vals:
            self._sync_team_manager_security_group()
        return result
