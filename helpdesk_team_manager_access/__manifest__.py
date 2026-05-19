{
    "name": "Helpdesk Team Manager Access",
    "summary": "Assign a manager per Helpdesk Team and grant access to that team's tickets.",
    "version": "17.0.1.0.0",
    "category": "Services/Helpdesk",
    "depends": ["helpdesk"],
    "data": [
        "security/helpdesk_team_manager_security.xml",
        "security/ir.model.access.csv",
        "views/helpdesk_team_views.xml",
        "views/helpdesk_ticket_transfer_views.xml",
        "views/helpdesk_ticket_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
