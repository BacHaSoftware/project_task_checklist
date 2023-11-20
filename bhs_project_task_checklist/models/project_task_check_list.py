# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProjectTask(models.Model):
    _inherit = 'project.task'

    checklist_ids = fields.One2many('task.checklist', 'task_id', required=True)

    def copy(self, default=None):
        default = default or {}
        new_task = super(ProjectTask, self).copy(default)
        for checklist in self.checklist_ids:
            # Copy o2m and assign new task
            checklist.copy(default={'task_id': new_task.id})
        return new_task

    def add_checklist_temp(self):
        return {
            'name': _('Add checklist'),
            'view_mode': 'form',
            'res_model': 'project.task.checklist.template',
            'type': 'ir.actions.act_window',
            'context': {'show_task': True, 'default_task_id': self.id},
            'target': 'new',
        }

    def reset_all_checklist(self):
        for task in self.filtered(lambda t: t.state != '1_done'):
            task.checklist_ids = [(2, line.id) for line in task.checklist_ids]

class TaskChecklist(models.Model):
    _name = 'task.checklist'
    _description = 'Checklist for the task'

    task_id = fields.Many2one('project.task')
    check_box = fields.Boolean(default=False)
    name = fields.Char(string='Title', required=True, index=True)
    sequence = fields.Integer('Sequence', default=0)
    # Categories
    is_title = fields.Boolean(default=False)
    title_id = fields.Many2one('task.checklist', string="Title", compute="_compute_title_id", store=True)
    line_ids = fields.One2many('task.checklist', "title_id", string="Line")

    @api.depends('task_id.checklist_ids.is_title', 'task_id.checklist_ids.sequence')
    def _compute_title_id(self):
        """ Will take all the slides of the channel for which the index is higher
        than the index of this category and lower than the index of the next category.

        Lists are manually sorted because when adding a new browse record order
        will not be correct as the added slide would actually end up at the
        first place no matter its sequence."""
        self.title_id = False  # initialize whatever the state

        tasks = {}
        for checklist in self:
            if checklist.task_id.id not in tasks:
                tasks[checklist.task_id.id] = checklist.task_id.checklist_ids

        for cid, checklists in tasks.items():
            current_title = self.env['task.checklist']
            checklist_list = list(checklists)
            checklist_list.sort(key=lambda s: (s.sequence, not s.is_title))
            for chk in checklist_list:
                if chk.is_title:
                    current_title = chk
                elif chk.title_id != current_title:
                    chk.title_id = current_title.id

    def name_get(self):
        res = []
        for checklist in self:
            name = checklist.name
            if self.env.context.get('show_task'):
                name = "%s (%s)" % (name, checklist.task_id.name)
            res += [(checklist.id, name)]
        return res



