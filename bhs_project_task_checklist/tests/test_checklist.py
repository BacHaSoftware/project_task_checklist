# -*- coding: utf-8 -*-
"""Checklist business flows and timesheet report tweaks."""
import importlib.util
import os
from datetime import date

from dateutil.relativedelta import relativedelta
from lxml import etree
from psycopg2 import IntegrityError

from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.tools.safe_eval import safe_eval

from .common import CHECKLIST, WIZARD, ChecklistCommon


@tagged('post_install', '-at_install')
class TestChecklistFlows(ChecklistCommon, TransactionCase):

    def test_form_add_title_and_content(self):
        """Project roles add a title and lines through the task form; lines are grouped under the preceding title."""
        for user in (self.admin, self.project_manager, self.project_user):
            with self.subTest(user=user.login):
                task = self.make_task(f'Form task {user.login}')
                with Form(task.with_user(user)) as form:
                    with form.checklist_ids.new() as title:
                        title.name = 'T1'
                        title.is_title = True
                        title.sequence = 1
                    with form.checklist_ids.new() as content:
                        content.name = 'C1'
                        content.sequence = 2
                    with form.checklist_ids.new() as content:
                        content.name = 'C2'
                        content.sequence = 3
                self.assertEqual(task.checklist_ids.sorted('sequence').mapped('name'), ['T1', 'C1', 'C2'])
                t1, c1, c2 = (self.line(task, n) for n in ('T1', 'C1', 'C2'))
                self.assertTrue(t1.is_title)
                self.assertFalse(t1.title_id)
                self.assertEqual((c1 | c2).title_id, t1)
                self.assertEqual(t1.line_ids, c1 | c2)

                # tick a line through the form (rows ordered by id: T1, C1, C2)
                with Form(task.with_user(user)) as form:
                    with form.checklist_ids.edit(1) as row:
                        row.check_box = True
                self.assertTrue(c1.check_box)
                self.assertFalse(c2.check_box)

    def test_form_save_task_without_checklist(self):
        """A task without checklist lines is saved through the form (an empty checklist is allowed)."""
        task = self.make_task('No checklist')
        with Form(task.with_user(self.project_user)) as form:
            form.name = 'No checklist (edited)'
        self.assertEqual(task.name, 'No checklist (edited)')
        self.assertFalse(task.checklist_ids)

    def test_title_is_nearest_preceding_title(self):  # _compute_title_id
        """title_id = nearest preceding title by sequence, recomputed after re-sequencing."""
        task = self.make_task('Order task', [
            ('T1', True, 1), ('C1', False, 2), ('T2', True, 3), ('C2', False, 4),
        ])
        t1, c1, t2, c2 = (self.line(task, n) for n in ('T1', 'C1', 'T2', 'C2'))
        self.assertEqual(c1.title_id, t1)
        self.assertEqual(c2.title_id, t2)

        c1.sequence = 5  # C1 dragged below T2
        self.assertEqual(c1.title_id, t2)
        self.assertEqual(t2.line_ids, c1 | c2)
        self.assertFalse(t1.line_ids)

        c2.sequence = 0  # above every title -> no title
        self.assertFalse(c2.title_id)

        c2.sequence = 3  # same sequence as T2: the title comes first
        self.assertEqual(c2.title_id, t2)

    def test_add_from_template(self):
        """Wizard on task B appends the chosen title of task A and its lines after B's last sequence."""
        source = self.make_task('Task A', [
            ('Release', True, 1), ('Build', False, 2), ('Deploy', False, 3), ('Other', True, 4), ('Skip', False, 5),
        ])
        target = self.make_task('Task B', [('Existing', False, 7, True)])
        action = target.with_user(self.project_user).add_checklist_temp()
        self.assertEqual(action['res_model'], WIZARD)
        self.assertEqual(action['target'], 'new')
        self.assertTrue(action['context'].get('show_task'))
        wizard_model = self.env[WIZARD].with_user(self.project_user).with_context(action['context'])
        with Form(wizard_model) as form:
            form.checklist_temp.add(self.line(source, 'Release'))
        wizard = form.record
        self.assertEqual(wizard.task_id, target)
        wizard.add_checklist()

        lines = target.checklist_ids.sorted('sequence')
        self.assertEqual(
            [(l.name, l.is_title, l.sequence, l.check_box) for l in lines],
            [('Existing', False, 7, True), ('Release', True, 8, False), ('Build', False, 9, False),
             ('Deploy', False, 10, False)],
        )
        self.assertEqual(lines.task_id, target, "Copied lines belong to the current task")
        release = self.line(target, 'Release')
        self.assertEqual((self.line(target, 'Build') | self.line(target, 'Deploy')).title_id, release)
        # source task untouched
        self.assertEqual(len(source.checklist_ids), 5)
        self.assertEqual(self.line(source, 'Release').line_ids.mapped('name'), ['Build', 'Deploy'])

    def test_add_from_template_empty_task(self):
        """Empty current task: sequences start at 1; several titles keep their order."""
        source = self.make_task('Task A2', [('Prepare', True, 1), ('Check', False, 2), ('Ship', True, 3)])
        target = self.make_task('Empty task')
        wizard = self.env[WIZARD].with_user(self.project_user).create({
            'task_id': target.id,
            'checklist_temp': [(6, 0, (self.line(source, 'Prepare') | self.line(source, 'Ship')).ids)],
        })
        wizard.add_checklist()
        self.assertEqual(
            [(l.name, l.sequence) for l in target.checklist_ids.sorted('sequence')],
            [('Prepare', 1), ('Check', 2), ('Ship', 3)],
        )

    def test_wizard_title_label_shows_task(self):  # _compute_display_name
        """Wizard (context show_task) labels a title 'Title (Task)'; without the context only the title."""
        task = self.make_task('Task A', [('Release', True, 1), ('Build', False, 2)])
        release = self.line(task, 'Release').with_user(self.project_user)
        self.assertEqual(release.display_name, 'Release')
        self.assertEqual(release.with_context(show_task=True).display_name, 'Release (Task A)')
        # autocomplete of the many2many_tags field of the wizard
        found = self.env[CHECKLIST].with_user(self.project_user).with_context(show_task=True).name_search(
            'Release', domain=[('is_title', '=', True), ('task_id', '=', task.id)])
        self.assertEqual(found, [(release.id, 'Release (Task A)')])

    def test_check_uncheck_clear_all(self):
        """Check all / Uncheck all / Clear all act on tasks in non-folded stages only,
        and Check all / Uncheck all on content lines only: section titles keep their check_box."""
        open_task = self.make_task('Open task', [('T', True, 1), ('C1', False, 2), ('C2', False, 3, True)])
        folded_task = self.make_task('Folded task', [('T', True, 1), ('C', False, 2)], stage=self.folded_stage)
        tasks = (open_task | folded_task).with_user(self.project_user)

        tasks.check_all_checklist()
        self.assertEqual(open_task.checklist_ids.mapped('check_box'), [False, True, True],
                         "Check all ticks the content lines, not the title")
        self.assertEqual(folded_task.checklist_ids.mapped('check_box'), [False, False])

        folded_task.checklist_ids.write({'check_box': True})
        self.line(open_task, 'T').check_box = True  # title ticked by another path (data written by RPC)
        tasks.uncheck_all_checklist()
        self.assertEqual(open_task.checklist_ids.mapped('check_box'), [True, False, False],
                         "Uncheck all unticks the content lines only")
        self.assertEqual(folded_task.checklist_ids.mapped('check_box'), [True, True])

        lines = open_task.checklist_ids
        tasks.reset_all_checklist()
        self.assertFalse(open_task.checklist_ids)
        self.assertFalse(lines.exists(), "Lines are deleted, not only unlinked from the task")
        self.assertEqual(len(folded_task.checklist_ids), 2)

    def test_duplicate_task_copies_checklist(self):
        """Copied task gets copies of the lines (same labels, ticks, titles), original unchanged."""
        task = self.make_task('Copy me', [('T1', True, 1), ('C1', False, 2, True), ('C2', False, 3)])
        original_lines = task.checklist_ids
        copy = task.with_user(self.project_manager).copy()
        self.assertNotEqual(copy, task)
        signature = lambda lines: sorted((l.name, l.is_title, l.sequence, l.check_box) for l in lines)  # noqa: E731
        self.assertEqual(signature(copy.checklist_ids), signature(original_lines))
        self.assertFalse(copy.checklist_ids & original_lines)
        self.assertEqual(task.checklist_ids, original_lines)
        self.assertEqual((self.line(copy, 'C1') | self.line(copy, 'C2')).title_id, self.line(copy, 'T1'),
                         "Copied lines point to the copied title, not the original one")

    def test_duplicate_several_tasks(self):
        """copy() on several tasks at once (e.g. project duplication): each copy gets its own checklist."""
        t1 = self.make_task('Multi 1', [('A', True, 1), ('A1', False, 2)])
        t2 = self.make_task('Multi 2', [('B', True, 1), ('B1', False, 2), ('B2', False, 3)])
        t3 = self.make_task('Multi 3')
        copies = (t1 | t2 | t3).with_user(self.project_manager).copy()
        self.assertEqual(len(copies), 3)
        by_origin = dict(zip((t1, t2, t3), copies))
        self.assertEqual(sorted(by_origin[t1].checklist_ids.mapped('name')), ['A', 'A1'])
        self.assertEqual(sorted(by_origin[t2].checklist_ids.mapped('name')), ['B', 'B1', 'B2'])
        self.assertFalse(by_origin[t3].checklist_ids)
        self.assertEqual(self.line(by_origin[t2], 'B2').title_id, self.line(by_origin[t2], 'B'))
        self.assertEqual(len(t1.checklist_ids) + len(t2.checklist_ids), 5, "Originals unchanged")

    def test_duplicate_project_copies_task_checklists(self):
        """Project duplication copies every task at once (core map_tasks): checklists follow."""
        self.make_task('P1', [('X', True, 1), ('X1', False, 2)])
        self.make_task('P2', [('Y', True, 1)])
        new_project = self.project.with_user(self.project_manager).copy()
        lines = new_project.task_ids.checklist_ids
        self.assertEqual(sorted(lines.mapped('name')), ['X', 'X1', 'Y'])

    # --- lines live and die with their task ----------------------------------------------------------------------

    def test_delete_task_deletes_its_lines(self):
        """Deleting a task deletes its lines: no line is left without a task (hidden from every user)."""
        task = self.make_task('Delete me', [('T', True, 1), ('C', False, 2)])
        lines = task.checklist_ids
        task.with_user(self.project_manager).unlink()
        self.assertFalse(lines.sudo().exists(), "Lines of a deleted task are deleted")
        self.assertFalse(self.env[CHECKLIST].sudo().search([('task_id', '=', False)]), "No line without a task")

    def test_delete_project_deletes_task_lines(self):
        """Deleting a project deletes its tasks and, with them, their lines (sub-tasks included)."""
        project = self.env['project.project'].create({'name': 'PTC delete project'})
        self.open_stage.project_ids = [(4, project.id)]
        parent = self.make_task('Del parent', [('P-T', True, 1), ('P-C', False, 2)], project=project)
        child = self.make_task('Del child', [('S-C', False, 1)], project=project)
        child.parent_id = parent
        lines = parent.checklist_ids | child.checklist_ids
        project.with_user(self.project_manager).unlink()
        self.assertFalse(lines.sudo().exists())
        self.assertFalse(self.env[CHECKLIST].sudo().search([('task_id', '=', False)]))

    def test_line_task_cannot_be_emptied(self):
        """write({'task_id': False}) is refused (required field) and the line keeps its task."""
        task = self.make_task('Keep task', [('C', False, 1)])
        line = task.checklist_ids
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            line.write({'task_id': False})
            line.flush_recordset()
        self.assertEqual(line.task_id, task)

    def test_line_cannot_be_created_without_task(self):
        """A line cannot be created without a task (required field)."""
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.env[CHECKLIST].create({'name': 'no task'})
        self.assertFalse(self.env[CHECKLIST].sudo().search([('name', '=', 'no task')]))

    # --- sub-task checklists follow duplication ------------------------------------------------------------------

    def _parent_with_subtask(self, project=None):
        parent = self.make_task('Sub parent', [('P-T', True, 1), ('P-C', False, 2)], project=project)
        child = self.make_task('Sub child', [('S-T', True, 1), ('S-C1', False, 2, True), ('S-C2', False, 3)],
                               project=project)
        child.parent_id = parent
        return parent, child

    def _assert_same_checklist(self, copy, source):
        signature = lambda lines: sorted(  # noqa: E731
            (l.name, l.is_title, l.sequence, l.check_box, l.title_id.name or '') for l in lines)
        self.assertEqual(signature(copy.checklist_ids), signature(source.checklist_ids))
        self.assertFalse(copy.checklist_ids & source.checklist_ids)
        self.assertLessEqual(copy.checklist_ids.title_id, copy.checklist_ids, "Titles of the copy are lines of the copy")

    def test_duplicate_task_copies_subtask_checklists(self):
        """Duplicating a task copies the checklist of its sub-tasks too (core copies children via copy_data)."""
        parent, child = self._parent_with_subtask()
        copy = parent.with_user(self.project_manager).copy()
        self.assertEqual(len(copy.child_ids), 1)
        self._assert_same_checklist(copy, parent)
        self._assert_same_checklist(copy.child_ids, child)
        self.assertEqual(self.line(copy.child_ids, 'S-C2').title_id, self.line(copy.child_ids, 'S-T'))
        self.assertEqual(len(parent.checklist_ids) + len(child.checklist_ids), 5, "Originals unchanged")

    def test_duplicate_project_copies_subtask_checklists(self):
        """Duplicating a project copies the checklists of its tasks and sub-tasks, each line once."""
        project = self.env['project.project'].create({'name': 'PTC copy sub project'})
        self.open_stage.project_ids = [(4, project.id)]
        parent, child = self._parent_with_subtask(project=project)
        new_project = project.with_user(self.project_manager).copy()
        new_parent = self.env['project.task'].search([('project_id', '=', new_project.id), ('parent_id', '=', False)])
        self.assertEqual(len(new_parent), 1)
        self.assertEqual(len(new_parent.child_ids), 1)
        self._assert_same_checklist(new_parent, parent)
        self._assert_same_checklist(new_parent.child_ids, child)

    # --- recurring tasks: the next occurrence starts with the same, unticked checklist --------------------------

    def test_recurring_next_occurrence_unticked_checklist(self):
        """Closing a recurring task creates the next occurrence (core copy_data): same lines, every tick cleared,
        for the sub-task too; the closed task keeps its ticks."""
        self.env.user.group_ids += self.env.ref('project.group_project_recurring_tasks')
        project = self.env['project.project'].create({'name': 'PTC recurring project', 'allow_recurring_tasks': True})
        self.open_stage.project_ids = [(4, project.id)]
        parent, child = self._parent_with_subtask(project=project)
        parent.write({'recurring_task': True, 'repeat_interval': 1, 'repeat_unit': 'week', 'repeat_type': 'forever'})
        (parent | child).checklist_ids.write({'check_box': True})
        parent.state = '1_done'
        occurrence = parent.recurrence_id.task_ids - parent
        self.assertEqual(len(occurrence), 1, "Closing the task creates the next occurrence")
        self.assertEqual(len(occurrence.child_ids), 1)
        signature = lambda lines: sorted(  # noqa: E731
            (l.name, l.is_title, l.sequence, l.title_id.name or '') for l in lines)
        for new, source in ((occurrence, parent), (occurrence.child_ids, child)):
            with self.subTest(task=source.name):
                self.assertEqual(signature(new.checklist_ids), signature(source.checklist_ids))
                self.assertFalse(new.checklist_ids & source.checklist_ids)
                self.assertFalse(any(new.checklist_ids.mapped('check_box')), "The next occurrence starts unticked")
                self.assertTrue(all(source.checklist_ids.mapped('check_box')), "The closed task keeps its ticks")

    def test_task_form_view_has_checklist_tab(self):
        """Form view of the task carries the checklist tab, the custom widget, the buttons and both create controls."""
        for user in (self.admin, self.project_manager, self.project_user, self.employee):
            with self.subTest(user=user.login):
                view = self.env['project.task'].with_user(user).get_view(
                    self.env.ref('project.view_task_form2').id, 'form')
                arch = etree.fromstring(view['arch'])
                for xpath in ("//page[@string='Checklist']",
                              "//field[@name='checklist_ids'][@widget='checklist_title_one2many']",
                              "//field[@name='checklist_ids']/list[@editable='bottom']",
                              "//create[@name='add_checklist_title']",
                              "//create[@name='add_checklist_content']",
                              "//button[@name='add_checklist_temp']",
                              "//button[@name='check_all_checklist'][@confirm]",
                              "//button[@name='uncheck_all_checklist'][@confirm]",
                              "//button[@name='reset_all_checklist'][@confirm]"):
                    with self.subTest(xpath=xpath):
                        self.assertTrue(arch.xpath(xpath))

    def test_field_labels_are_distinct(self):
        """name keeps the label of its column in the task form (Title); title_id has its own label (Section),
        so no two fields of task.checklist share a label (Odoo warns at every install/update otherwise)."""
        fields = self.env[CHECKLIST].fields_get(attributes=['string'])
        self.assertEqual(fields['name']['string'], 'Title')
        self.assertEqual(fields['title_id']['string'], 'Section')
        labels = [f['string'] for f in fields.values()]
        self.assertEqual(sorted(set(l for l in labels if labels.count(l) > 1)), [])

    def test_checklist_list_and_wizard_views(self):
        list_arch = etree.fromstring(self.env[CHECKLIST].get_view(
            self.env.ref('bhs_project_task_checklist.task_checklist_tree_view').id, 'list')['arch'])
        self.assertEqual(list_arch.tag, 'list')
        wizard_arch = etree.fromstring(self.env[WIZARD].get_view(
            self.env.ref('bhs_project_task_checklist.project_task_checklist_template_view_form').id, 'form')['arch'])
        field = wizard_arch.xpath("//field[@name='checklist_temp']")[0]
        self.assertEqual(field.get('widget'), 'many2many_tags')
        self.assertIn('show_task', field.get('context'))
        self.assertTrue(wizard_arch.xpath("//button[@name='add_checklist']"))


@tagged('post_install', '-at_install')
class TestPreMigrate(ChecklistCommon, TransactionCase):
    """migrations/20.0.1.0.1/pre-migrate.py deletes the lines left without a task before NOT NULL is set."""

    VERSION = '20.0.1.0.1'

    def _load_migration(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', self.VERSION, 'pre-migrate.py')
        spec = importlib.util.spec_from_file_location('ptc_pre_migrate_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _orphan(self):
        """A line without a task, as left by 20.0.1.0.0 (column still nullable there)."""
        self.env.flush_all()
        self.env.cr.execute("ALTER TABLE task_checklist ALTER COLUMN task_id DROP NOT NULL")
        self.env.cr.execute("""INSERT INTO task_checklist (name, sequence, check_box, is_title)
                               VALUES ('orphan', 1, false, false) RETURNING id""")
        return self.env.cr.fetchone()[0]

    def _exists(self, line_id):
        self.env.cr.execute("SELECT 1 FROM task_checklist WHERE id = %s", [line_id])
        return bool(self.env.cr.fetchone())

    def test_upgrade_deletes_lines_without_task_and_logs_count(self):
        task = self.make_task('Kept task', [('Kept', False, 1)])
        kept = task.checklist_ids
        orphan_id = self._orphan()
        migration = self._load_migration()
        with self.assertLogs(migration.__name__, 'INFO') as logs:
            migration.migrate(self.env.cr, '20.0.1.0.0')
        self.assertFalse(self._exists(orphan_id), "The line without a task is deleted")
        self.assertTrue(self._exists(kept.id), "Lines of a task are kept")
        self.assertIn('task.checklist: 1 line(s) without a task deleted', ' '.join(logs.output))

    def test_install_does_not_run_cleanup(self):
        orphan_id = self._orphan()
        self._load_migration().migrate(self.env.cr, False)
        self.assertTrue(self._exists(orphan_id), "Nothing to clean on a fresh install (version is empty)")


@tagged('post_install', '-at_install')
class TestPostMigrateUntickTitles(ChecklistCommon, TransactionCase):
    """migrations/20.0.1.0.2/post-migrate.py unticks the section titles ticked by the old Check all:
    Uncheck all skips titles and a title row has no checkbox, so such a tick could not be removed any more."""

    def _load_migration(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '20.0.1.0.2', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ptc_post_migrate_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _ticked_title_task(self):
        task = self.make_task('Old check all', [('T', True, 1, True), ('C1', False, 2, True), ('C2', False, 3)])
        self.env.flush_all()
        return task

    def test_upgrade_unticks_titles_and_logs_count(self):
        task = self._ticked_title_task()
        migration = self._load_migration()
        with self.assertLogs(migration.__name__, 'INFO') as logs:
            migration.migrate(self.env.cr, '20.0.1.0.1')
        task.checklist_ids.invalidate_recordset(['check_box'])
        self.assertEqual(task.checklist_ids.sorted('sequence').mapped('check_box'), [False, True, False],
                         "Titles are unticked, content ticks are kept")
        self.assertIn('task.checklist: 1 section title(s) unticked', ' '.join(logs.output))

    def test_install_does_not_run_untick(self):
        task = self._ticked_title_task()
        self._load_migration().migrate(self.env.cr, False)
        task.checklist_ids.invalidate_recordset(['check_box'])
        self.assertEqual(task.checklist_ids.sorted('sequence').mapped('check_box'), [True, True, False],
                         "Nothing to do on a fresh install (version is empty)")


@tagged('post_install', '-at_install')
class TestTimesheetReport(TransactionCase):
    """Timesheet report action context, filters and pivot column added by the module."""

    def _search_filters(self, model, view_xmlid):
        arch = self.env[model].get_view(self.env.ref(view_xmlid).id, 'search')['arch']
        return {f.get('name'): f for f in etree.fromstring(arch).iter('filter')}

    def test_report_action_context(self):
        context = safe_eval(self.env.ref('hr_timesheet.act_hr_timesheet_report').context)
        self.assertEqual(context, {
            'search_default_groupby_employee_first': 1,
            'search_default_groupby_task': 1,
            'search_default_current_month': 1,
        })

    def test_month_filters_domain(self):
        today = date(2026, 2, 14)
        eval_context = {'context_today': lambda: today, 'relativedelta': relativedelta, 'uid': self.env.uid}
        for model, view in (('account.analytic.line', 'hr_timesheet.hr_timesheet_line_search'),
                            ('timesheets.analysis.report', 'hr_timesheet.hr_timesheet_report_search')):
            with self.subTest(model=model):
                filters = self._search_filters(model, view)
                self.assertIn('groupby_employee_first', filters)
                self.assertIn('groupby_task', filters)
                self.assertEqual(safe_eval(filters['current_month'].get('domain'), eval_context),
                                 [('date', '<', '2026-03-01'), ('date', '>=', '2026-02-01')])
                self.assertEqual(safe_eval(filters['my_time_sheet_this_month'].get('domain'), eval_context),
                                 [('date', '<', '2026-03-01'), ('date', '>=', '2026-02-01'),
                                  ('user_id', '=', self.env.uid)])

    def test_pivot_has_day_column(self):
        arch = self.env['account.analytic.line'].get_view(
            self.env.ref('hr_timesheet.view_hr_timesheet_line_pivot').id, 'pivot')['arch']
        self.assertTrue(etree.fromstring(arch).xpath("//field[@name='date'][@interval='day'][@type='col']"))
