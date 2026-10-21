# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # not required: meaningless on a one2many (a task may have no checklist)
    # copy=True: lines are copied by copy_data(), which core also uses for sub-tasks (copy() is not called on them)
    checklist_ids = fields.One2many('task.checklist', 'task_id', copy=True)

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
        for task in self.filtered(lambda t: not t.stage_id.fold):
            task.checklist_ids = [(2, line.id) for line in task.checklist_ids]

    def check_all_checklist(self):
        # Section titles are not items to do: only content lines are ticked
        for task in self.filtered(lambda t: not t.stage_id.fold):
            task.checklist_ids.filtered(lambda line: not line.is_title).write({'check_box': True})

    def uncheck_all_checklist(self):
        for task in self.filtered(lambda t: not t.stage_id.fold):
            task.checklist_ids.filtered(lambda line: not line.is_title).write({'check_box': False})


class ProjectTaskRecurrence(models.Model):
    _inherit = 'project.task.recurrence'

    @api.model
    def _create_next_occurrences_values(self, recurrence_by_task):
        # The next occurrence gets the checklist through copy_data(): same lines, every tick cleared.
        # Core builds the sub-task values with this same method, so sub-task occurrences are reset too.
        return [
            {**vals, 'checklist_ids': [_unticked(command) for command in vals['checklist_ids']]}
            if vals.get('checklist_ids') else vals
            for vals in super()._create_next_occurrences_values(recurrence_by_task)
        ]


def _unticked(command):
    """Copy of a one2many create command with check_box False; other commands are returned unchanged."""
    if command[0] == Command.CREATE:
        return Command.create({**command[2], 'check_box': False})
    return command


class TaskChecklist(models.Model):
    _name = 'task.checklist'
    _description = 'Checklist for the task'

    # A line lives and dies with its task: a line without a task would be hidden from every user (access follows the task)
    task_id = fields.Many2one('project.task', required=True, ondelete='cascade')
    check_box = fields.Boolean(default=False)
    # copy=True: Odoo 20 suffixes a copied 'name' with " (copy)" unless copy is declared
    name = fields.Char(string='Title', required=True, index=True, copy=True)
    sequence = fields.Integer('Sequence', default=0)
    # Categories
    is_title = fields.Boolean('Is a title', default=False)
    # Label differs from name ('Title', the column of the task form list): Odoo warns about duplicate labels
    title_id = fields.Many2one('task.checklist', string="Section", compute="_compute_title_id", store=True)
    line_ids = fields.One2many('task.checklist', "title_id", string="Line")

    @api.depends('task_id.checklist_ids.is_title', 'task_id.checklist_ids.sequence')
    def _compute_title_id(self):
        """Nearest preceding title by sequence. Lines are sorted by hand: a new record is not yet in its
        sequence order."""
        self.title_id = False

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

    def write(self, vals):
        # Access rules are checked on the lines before the write: moving a line into another task
        # requires write access on that task as well
        if vals.get('task_id'):
            self.env['project.task'].browse(vals['task_id']).check_access('write')
        return super().write(vals)

    @api.depends('name', 'task_id.name')
    @api.depends_context('show_task')
    def _compute_display_name(self):
        # Odoo 20: name_get() is gone, the wizard labels a title "Title (Task)" here
        show_task = self.env.context.get('show_task')
        for checklist in self:
            if show_task and checklist.task_id:
                checklist.display_name = f"{checklist.name} ({checklist.task_id.name})"
            else:
                checklist.display_name = checklist.name
