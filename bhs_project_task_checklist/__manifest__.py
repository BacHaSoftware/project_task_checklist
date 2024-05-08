{
    'name': "Project Task Check List",
    'version': '17.0.1.0.0',
    'summary': """Check-list task""",
    'description': """Create and check task completion on the basis of checklists""",
    'category': 'Project',
    'author': 'Bac Ha Software',
    'company': 'Bac Ha Software',
    'maintainer': 'Bac Ha Software',
    'website': "https://bachasoftware.com",
    'depends': ['project', 'base', 'hr_timesheet'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_check_list.xml',
        'wizard/project_task_checklist_template_view.xml',
        'report/project_task_report.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'bhs_project_task_checklist/static/src/scss/project_check_list.scss',
            'bhs_project_task_checklist/static/src/js/checklist_title_list_renderer.js',
            'bhs_project_task_checklist/static/src/js/checklist_title_one2many_field.js',
        ]
    },

    'images': ['static/description/banner.gif'],
    'license': "AGPL-3",
    'installable': True,
    'application': True,
}
