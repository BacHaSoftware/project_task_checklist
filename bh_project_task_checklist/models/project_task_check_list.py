# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    checklist_ids = fields.One2many('task.checklist', 'task_id', required=True)

class TaskChecklist(models.Model):
    _name = 'task.checklist'
    _description = 'Checklist for the task'

    task_id = fields.Many2one('project.task')
    check_box = fields.Boolean(default=False)
    name = fields.Char(string='Title', required=True, index=True)




