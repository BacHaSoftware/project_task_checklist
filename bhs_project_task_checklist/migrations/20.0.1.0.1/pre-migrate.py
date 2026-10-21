# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """task.checklist.task_id becomes required with ON DELETE CASCADE.

    Lines left without a task (task deleted, or task_id emptied) are hidden from every user and cannot be
    reached any more: delete them so that the NOT NULL constraint can be set.
    """
    if not version:
        return
    cr.execute("DELETE FROM task_checklist WHERE task_id IS NULL")
    _logger.info("task.checklist: %s line(s) without a task deleted", cr.rowcount)
