# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Check all no longer ticks section titles and Uncheck all skips them.

    A title ticked by the old Check all would stay struck through for good (a title row has no checkbox):
    untick every title.
    """
    if not version:
        return
    cr.execute("UPDATE task_checklist SET check_box = false WHERE is_title AND check_box")
    _logger.info("task.checklist: %s section title(s) unticked", cr.rowcount)
