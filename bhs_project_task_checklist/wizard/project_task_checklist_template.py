# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProjectTaskChecklistTemplate(models.TransientModel):
    _name = 'project.task.checklist.template'
    _description = 'Project task checklist template'

    checklist_temp = fields.Many2many('task.checklist', string="Choose Checklist")
    task_id = fields.Many2one('project.task')

    def add_checklist(self):
        vals = []
        current_sequence = max(self.task_id.checklist_ids.mapped('sequence')) if self.task_id.checklist_ids else 0
        # task_id of the new lines is set by the one2many inverse (current task)
        for record in self.checklist_temp:
            current_sequence += 1
            vals.append((0, 0, {'name': record.name,
                                'is_title': record.is_title,
                                'sequence': current_sequence}))

            for line in record.line_ids:
                current_sequence += 1
                vals.append((0, 0, {'name': line.name,
                                    'is_title': line.is_title,
                                    'sequence': current_sequence}))

        self.task_id.checklist_ids = vals
