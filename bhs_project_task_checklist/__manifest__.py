{
    'name': "Task Check List",
    'version': '20.0.1.0.2',
    'summary': """Check-list task""",
    'description': """Create and check task completion on the basis of checklists""",
    'category': 'Project',
    'author': 'Bac Ha Software',
    'company': 'Bac Ha Software',
    'maintainer': 'Bac Ha Software',
    'website': "https://bachasoftware.com",
    'depends': ['project', 'base', 'hr_timesheet'],
    # same models and widget under another name: the two modules cannot be installed together
    'excludes': ['bhs_task_execution_organizer'],
    'data': [
        'views/project_check_list.xml',
        'wizard/project_task_checklist_template_view.xml',
        'report/project_task_report.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'bhs_project_task_checklist/static/src/css/project_check_list.scss',
            'bhs_project_task_checklist/static/src/js/checklist_title_list_renderer.js',
            'bhs_project_task_checklist/static/src/js/checklist_title_one2many_field.js',
        ],
        'web.assets_tests': [
            'bhs_project_task_checklist/static/tests/tours/**/*',
        ],
    },

    'images': ['static/description/banner.gif'],
    'license': 'LGPL-3',
    'installable': True,
    'application': True
}
