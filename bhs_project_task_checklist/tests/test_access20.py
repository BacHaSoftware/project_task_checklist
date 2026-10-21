# -*- coding: utf-8 -*-
"""Access to task.checklist and to the "Add checklist" wizard per role.

Rule: read a checklist line if the user can read its task; create/write/delete it if the user can write the task.
Users without access to the task (internal users on private projects, portal) get AccessError.
Each "cannot" test has its "can" counterpart.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from .common import CHECKLIST, WIZARD, ChecklistCommon


@tagged('post_install', '-at_install')
class TestChecklistAccess(ChecklistCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task = cls.make_task('Shared task', [('T', True, 1), ('C', False, 2)])
        cls.private_task = cls.make_task('Private task', [('PT', True, 1), ('PC', False, 2)],
                                         project=cls.private_project)
        cls.portal_task = cls.make_task('Portal task', [('XT', True, 1), ('XC', False, 2)],
                                        project=cls.portal_project)
        cls.portal_task.message_subscribe(partner_ids=cls.portal.partner_id.ids)

    # --- helpers -------------------------------------------------------------------------------------------------

    def _assert_full_access(self, user, task):
        lines = task.checklist_ids.with_user(user)
        self.assertEqual(sorted(lines.mapped('name')), sorted(task.checklist_ids.mapped('name')))
        self.assertEqual(self.env[CHECKLIST].with_user(user).search([('task_id', '=', task.id)]), task.checklist_ids)
        line = self.env[CHECKLIST].with_user(user).create({
            'task_id': task.id, 'name': f'by {user.login}', 'sequence': 3,
        })
        line.write({'check_box': True})
        self.assertTrue(line.check_box)
        self.assertEqual(line.title_id, task.checklist_ids.filtered('is_title')[:1])
        line.unlink()
        self.assertFalse(line.exists())

    def _assert_no_access(self, user, task):
        lines = task.checklist_ids
        Checklist = self.env[CHECKLIST].with_user(user)
        self.assertFalse(Checklist.search([('task_id', '=', task.id)]), "Lines of the task must not be listed")
        with self.assertRaises(AccessError):
            lines.with_user(user).read(['name'])
        with self.assertRaises(AccessError):
            Checklist.create({'task_id': task.id, 'name': 'intruder'})
        with self.assertRaises(AccessError):
            lines.with_user(user).write({'check_box': True})
        with self.assertRaises(AccessError):
            lines.with_user(user).unlink()
        self.assertEqual(len(lines.exists()), 2)
        self.assertFalse(any(lines.mapped('check_box')))

    # --- project roles: full access on tasks they can write -------------------------------------------------------

    def test_admin_full_access(self):
        self._assert_full_access(self.admin, self.task)
        self._assert_full_access(self.admin, self.private_task)

    def test_project_manager_full_access(self):
        self._assert_full_access(self.project_manager, self.task)
        self._assert_full_access(self.project_manager, self.private_task)

    def test_project_user_full_access_on_visible_task(self):
        self._assert_full_access(self.project_user, self.task)

    def test_project_user_follower_of_private_task(self):
        """A project user who follows a task of a private project works on its checklist (core task rule)."""
        self.private_task.message_subscribe(partner_ids=self.project_user.partner_id.ids)
        self._assert_full_access(self.project_user, self.private_task)

    def test_project_user_no_access_to_private_task(self):
        self._assert_no_access(self.outsider_project_user, self.private_task)

    # --- employee: reads checklists of tasks it can read, cannot change them ------------------------------------

    def test_employee_reads_checklist_of_readable_task(self):
        task = self.task.with_user(self.employee)
        self.assertEqual(sorted(task.checklist_ids.mapped('name')), ['C', 'T'])
        lines = self.env[CHECKLIST].with_user(self.employee).search([('task_id', '=', self.task.id)])
        self.assertEqual(lines, self.task.checklist_ids)
        self.assertEqual(self.line(self.task, 'C').with_user(self.employee).title_id.name, 'T')

    def test_employee_cannot_change_checklist_of_readable_task(self):
        lines = self.task.checklist_ids
        Checklist = self.env[CHECKLIST].with_user(self.employee)
        with self.assertRaises(AccessError):
            lines.with_user(self.employee).write({'check_box': True})
        with self.assertRaises(AccessError):
            Checklist.create({'task_id': self.task.id, 'name': 'employee line'})
        with self.assertRaises(AccessError):
            lines.with_user(self.employee).unlink()
        with self.assertRaises(AccessError):
            self.task.with_user(self.employee).check_all_checklist()
        with self.assertRaises(AccessError):
            self.task.with_user(self.employee).reset_all_checklist()
        self.assertEqual(len(lines.exists()), 2)
        self.assertFalse(any(lines.mapped('check_box')))

    # --- internal user without access to the task ------------------------------------------------------------------

    def test_outsider_cannot_access_private_task_checklist(self):
        self._assert_no_access(self.outsider, self.private_task)

    def test_outsider_reads_checklist_of_public_task(self):
        """Counterpart: the same user reads the checklist of a task of an 'All internal users' project."""
        self.assertEqual(self.task.checklist_ids.with_user(self.outsider).mapped('name'), ['T', 'C'])

    def test_project_user_cannot_move_line_to_unwritable_task(self):
        """A line of a task the user can write cannot be moved into a task the user cannot write."""
        line = self.env[CHECKLIST].with_user(self.project_user).create({'task_id': self.task.id, 'name': 'mine'})
        with self.assertRaises(AccessError):
            line.write({'task_id': self.private_task.id})

    # --- portal ------------------------------------------------------------------------------------------------------

    def test_portal_reads_its_task_but_not_the_checklist(self):
        """Counterpart: the portal collaborator reads the task itself, never its checklist lines."""
        self.assertEqual(self.portal_task.with_user(self.portal).name, 'Portal task')
        with self.assertRaises(AccessError):
            self.env[CHECKLIST].with_user(self.portal).search([])
        self._assert_portal_denied(self.portal_task)
        self._assert_portal_denied(self.task)

    def _assert_portal_denied(self, task):
        lines = task.checklist_ids
        with self.assertRaises(AccessError):
            lines.with_user(self.portal).read(['name'])
        with self.assertRaises(AccessError):
            self.env[CHECKLIST].with_user(self.portal).create({'task_id': task.id, 'name': 'portal line'})
        with self.assertRaises(AccessError):
            lines.with_user(self.portal).write({'check_box': True})
        with self.assertRaises(AccessError):
            self.env[WIZARD].with_user(self.portal).create({'task_id': task.id})

    # --- "Add checklist" wizard ------------------------------------------------------------------------------------

    def test_wizard_usable_by_task_writers(self):
        for user in (self.admin, self.project_manager, self.project_user):
            with self.subTest(user=user.login):
                target = self.make_task(f'Wizard target {user.login}')
                wizard = self.env[WIZARD].with_user(user).create({
                    'task_id': target.id, 'checklist_temp': [(6, 0, self.line(self.task, 'T').ids)],
                })
                wizard.add_checklist()
                self.assertEqual(sorted(target.checklist_ids.mapped('name')), ['C', 'T'])

    def test_wizard_denied_without_task_write(self):
        Wizard = self.env[WIZARD]
        with self.assertRaises(AccessError):
            Wizard.with_user(self.employee).create({'task_id': self.task.id})
        with self.assertRaises(AccessError):
            Wizard.with_user(self.outsider).create({'task_id': self.private_task.id})
        self.assertEqual(len(self.task.checklist_ids), 2)

    def test_wizard_cannot_copy_titles_of_unreadable_task(self):
        """The template list only offers titles of tasks the user can read; a hidden title cannot be copied."""
        hidden_title = self.line(self.private_task, 'PT')
        titles = self.env[CHECKLIST].with_user(self.project_user).search([('is_title', '=', True)])
        self.assertNotIn(hidden_title, titles)
        self.assertIn(self.line(self.task, 'T'), titles)
        target = self.make_task('Wizard target hidden')
        with self.assertRaises(AccessError):
            wizard = self.env[WIZARD].with_user(self.project_user).create({
                'task_id': target.id, 'checklist_temp': [(6, 0, hidden_title.ids)],
            })
            wizard.add_checklist()
        self.assertFalse(target.checklist_ids)
