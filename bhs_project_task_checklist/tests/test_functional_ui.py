# -*- coding: utf-8 -*-
"""UI-level functional tests.

- Clickbot (tag click_all, run explicitly: $T test --db <db> --clickbot bhs_project_task_checklist): Odoo's clickbot
  clicks every menu of the Project app (where the module adds the Checklist tab on the task form), switches views,
  opens forms, creates records and clicks filters as admin, project manager and project user. The Timesheets app is
  not clicked: core 20 menu Reporting > By Project times out on "open form view from list" (action without form
  view, not touched by the module); the timesheet tweaks are covered
  by test_checklist.TestTimesheetReport and TestOpenActions below.
- Browser tour (standard suite): a project user saves a task without checklist, adds a title and a content line,
  saves, then uses "Check all" (checklist_title_one2many widget, OWL 3).
- TestOpenActions (standard suite): the actions/views the module changes are loaded over HTTP (JSON-RPC) per role.
"""
from odoo.tests import HttpCase, tagged

MODULE = 'bhs_project_task_checklist'
APPS: list[str] = ['project.menu_main_pm']
ROLES = {
    'click_ptc_admin': ['base.group_user', 'base.default_user_group', 'base.group_system',
                        'project.group_project_manager', 'hr_timesheet.group_timesheet_manager'],
    'click_ptc_manager': ['base.group_user', 'base.default_user_group', 'project.group_project_manager',
                          'hr_timesheet.group_hr_timesheet_approver'],
    'click_ptc_user': ['base.group_user', 'base.default_user_group', 'project.group_project_user',
                       'hr_timesheet.group_hr_timesheet_user'],
}
TZ = 'Asia/Ho_Chi_Minh'


class UiMixin:
    module = MODULE

    def _make_user(self, login, groups):
        group_ids = [self.env.ref(g).id for g in groups]
        existing = self.env['res.users'].search([('login', '=', login)])
        if existing:
            # login already exists (previous run): RESET the role's groups and password
            existing.write({'group_ids': [(6, 0, group_ids)], 'password': login})
            return existing
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'password': login, 'email': f'{login}@click.example.com', 'tz': TZ,
            'group_ids': [(6, 0, group_ids)],
        })

    def _seed_task(self, name, user=None, lines=True):
        project = self.env['project.project'].create({'name': f'{name} project', 'privacy_visibility': 'employees'})
        return self.env['project.task'].create({
            'name': name,
            'project_id': project.id,
            'user_ids': [(6, 0, user.ids)] if user else False,
            'checklist_ids': [
                (0, 0, {'name': 'Prepare', 'is_title': True, 'sequence': 1}),
                (0, 0, {'name': 'Write spec', 'sequence': 2, 'check_box': True}),
                (0, 0, {'name': 'Review', 'sequence': 3}),
            ] if lines else [],
        })

    def run_clickbot(self, roles, apps=None):
        apps = apps or APPS
        for login, groups in roles.items():
            user = self._make_user(login, groups)
            visible = self.env['ir.ui.menu'].with_user(user)
            for xmlid in apps:
                self.assertIn(self.env.ref(xmlid).id, visible._visible_menu_ids(),
                              f"Role {login} must see app {xmlid}")
                with self.subTest(role=login, app=xmlid):
                    self.browser_js(
                        '/odoo',
                        "odoo.loader.modules.get('@web/webclient/clickbot/clickbot_loader')"
                        f".startClickEverywhere({{ xmlId: '{xmlid}', logger: true }});",
                        login=login, timeout=1800, success_signal='clickbot test succeeded')


@tagged('click_all', 'post_install', '-at_install', '-standard')
class TestFunctionalUI(UiMixin, HttpCase):

    def test_clickbot_module_apps(self):
        users = {login: self._make_user(login, groups) for login, groups in ROLES.items()}
        task = self._seed_task('Clickbot task', users['click_ptc_user'])
        employee = self.env['hr.employee'].create({'name': 'Click PTC employee', 'user_id': users['click_ptc_user'].id})
        self.env['account.analytic.line'].create({
            'name': 'Checklist work', 'project_id': task.project_id.id, 'task_id': task.id,
            'employee_id': employee.id, 'unit_amount': 1.5,
        })
        self.run_clickbot(ROLES)


@tagged('post_install', '-at_install')
class TestChecklistTour(UiMixin, HttpCase):
    """Main checklist flow through a real browser."""

    def test_project_user_checklist_tour(self):
        user = self._make_user('tour_ptc_user', ROLES['click_ptc_user'])
        task = self._seed_task('Tour task', lines=False)
        self.start_tour(f'/odoo/action-project.action_view_all_task/{task.id}', 'bhs_ptc_checklist_tour',
                        login=user.login)
        self.assertEqual(task.name, 'Tour task edited', "The task was saved while its checklist was empty")
        lines = task.checklist_ids.sorted('sequence')
        self.assertEqual([(l.name, l.is_title, l.check_box) for l in lines], [('T1', True, False), ('C1', False, True)],
                         "Check all ticks the content line, not the title")
        title, content = lines
        self.assertEqual(content.title_id, title)


@tagged('post_install', '-at_install')
class TestOpenActions(UiMixin, HttpCase):
    """Views and actions changed by the module load over HTTP for each role."""

    def _call(self, model, method, args, kwargs=None):
        return self.make_jsonrpc_request('/web/dataset/call_kw', {
            'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {},
        })

    def test_roles_open_task_form_and_reports(self):
        task = self._seed_task('Action task')
        for login, groups in ROLES.items():
            with self.subTest(role=login):
                self._make_user(login, groups)
                self.authenticate(login, login)
                views = self._call('project.task', 'get_views', [], {
                    'views': [[self.env.ref('project.view_task_form2').id, 'form']], 'options': {}})
                self.assertIn('checklist_ids', views['views']['form']['arch'])
                data = self._call('project.task', 'web_read', [[task.id]], {'specification': {
                    'checklist_ids': {'fields': {'name': {}, 'is_title': {}, 'check_box': {}, 'sequence': {}}},
                }})
                self.assertEqual([l['name'] for l in sorted(data[0]['checklist_ids'], key=lambda l: l['sequence'])],
                                 ['Prepare', 'Write spec', 'Review'])
                action = self.make_jsonrpc_request('/web/action/load', {
                    'action_id': 'hr_timesheet.act_hr_timesheet_report'})
                self.assertIn('search_default_current_month', action['context'])
                pivot = self._call('account.analytic.line', 'get_views', [], {
                    'views': [[self.env.ref('hr_timesheet.view_hr_timesheet_line_pivot').id, 'pivot'],
                              [self.env.ref('hr_timesheet.hr_timesheet_line_search').id, 'search']],
                    'options': {}})
                self.assertIn('interval="day"', pivot['views']['pivot']['arch'])
                self.assertIn('my_time_sheet_this_month', pivot['views']['search']['arch'])
                wizard = self._call('project.task.checklist.template', 'get_views', [], {
                    'views': [[False, 'form']], 'options': {}})
                self.assertIn('checklist_temp', wizard['views']['form']['arch'])
