# -*- coding: utf-8 -*-
"""Shared fixtures: one user per role and tasks with different visibility.

Roles (access to task.checklist follows its task):
- admin: Settings + Project administrator
- project manager / project user: core Project groups
- employee: internal user without Project rights (reads tasks of 'employees' projects, cannot write them)
- outsider: internal user without access to the task (private 'followers' project, not a follower)
- portal: portal user (collaborator of a portal project, follower of its task)
"""
from odoo.tests import new_test_user

CHECKLIST = 'task.checklist'
WIZARD = 'project.task.checklist.template'


class ChecklistCommon:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def user(login, groups):
            return new_test_user(cls.env, login=login, email=f'{login}@example.com', groups=groups)

        cls.admin = user('ptc_admin', 'base.group_user,base.group_system,project.group_project_manager')
        cls.project_manager = user('ptc_project_manager', 'base.group_user,project.group_project_manager')
        cls.project_user = user('ptc_project_user', 'base.group_user,project.group_project_user')
        cls.employee = user('ptc_employee', 'base.group_user')
        cls.outsider = user('ptc_outsider', 'base.group_user')
        cls.outsider_project_user = user('ptc_outsider_pu', 'base.group_user,project.group_project_user')
        cls.portal = user('ptc_portal', 'base.group_portal')

        Project = cls.env['project.project']
        cls.project = Project.create({'name': 'PTC project', 'privacy_visibility': 'employees'})
        cls.private_project = Project.create({'name': 'PTC private project', 'privacy_visibility': 'followers'})
        cls.portal_project = Project.create({'name': 'PTC portal project', 'privacy_visibility': 'portal'})
        cls.portal_project._add_collaborators(cls.portal.partner_id)

        Stage = cls.env['project.task.type']
        cls.open_stage = Stage.create({
            'name': 'PTC open', 'fold': False,
            'project_ids': [(4, p.id) for p in (cls.project, cls.private_project, cls.portal_project)],
        })
        cls.folded_stage = Stage.create({'name': 'PTC done', 'fold': True, 'project_ids': [(4, cls.project.id)]})

    @classmethod
    def make_task(cls, name, lines=(), stage=None, project=None):
        """lines: iterable of (name, is_title, sequence) or (name, is_title, sequence, check_box)."""
        commands = []
        for line in lines:
            n, is_title, seq, *rest = line
            commands.append((0, 0, {'name': n, 'is_title': is_title, 'sequence': seq,
                                    'check_box': bool(rest and rest[0])}))
        return cls.env['project.task'].create({
            'name': name,
            'project_id': (project or cls.project).id,
            'stage_id': (stage or cls.open_stage).id,
            'checklist_ids': commands,
        })

    @staticmethod
    def line(task, name):
        return task.checklist_ids.filtered(lambda l: l.name == name)
