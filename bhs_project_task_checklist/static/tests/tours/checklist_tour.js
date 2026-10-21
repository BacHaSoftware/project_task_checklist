import { registry } from "@web/core/registry";

/**
 * Project user on a task without checklist lines:
 * 1. edits the task title and saves (a task without checklist lines can be saved);
 * 2. tab Checklist: adds a title "T1" and a content line "C1" with the checklist_title_one2many widget, saves;
 * 3. "Check all" (confirmation dialog) ticks the content line (not the title), which is shown muted.
 * Saved rows (C1.title_id = T1, C1 ticked, T1 not) are checked on the Python side (tests/test_functional_ui.py).
 */
const field = ".o_field_widget[name=checklist_ids]";
const editedName = `${field} .o_data_row.o_selected_row .o_field_widget[name=name] input`;
// Selected row that is not a title: waits until the new content row replaces the title row in edition
const editedContentName = `${field} .o_data_row.o_selected_row:not(.o_is_section) .o_field_widget[name=name] input`;

registry.category("web_tour.tours").add("bhs_ptc_checklist_tour", {
    steps: () => [
        {
            content: "Edit the task title",
            trigger: ".o_form_view .o_task_name textarea",
            run: "edit Tour task edited && press Tab",
        },
        {
            content: "Form is dirty",
            trigger: ".o_form_dirty",
        },
        {
            content: "Save the task while its checklist is empty",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Saved",
            trigger: ".o_form_saved",
        },
        {
            content: "Open the Checklist tab",
            trigger: ".o_notebook .nav-link:contains(Checklist)",
            run: "click",
        },
        {
            content: "Checklist table uses the section list renderer",
            trigger: `${field} table.o_section_list_view`,
        },
        {
            content: "Add a title",
            trigger: `${field} .o_field_x2many_list_row_add button:contains(Add Title)`,
            run: "click",
        },
        {
            content: "Title name",
            trigger: editedName,
            run: "edit T1",
        },
        {
            content: "Add a content line",
            trigger: `${field} .o_field_x2many_list_row_add button:contains(Add Content)`,
            run: "click",
        },
        {
            content: "Content name",
            trigger: editedContentName,
            run: "edit C1",
        },
        {
            content: "Title row is a bold section spanning the columns",
            trigger: `${field} tr.o_data_row.o_is_section.fw-bold td[name=name][colspan]:contains(T1)`,
        },
        {
            content: "Save the task",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Wait for save completion",
            trigger: ".o_form_saved",
        },
        {
            content: "Content row is a normal row after save",
            trigger: `${field} tr.o_data_row:not(.o_is_section) td[name=name]:contains(C1)`,
        },
        {
            content: "Check all",
            trigger: "button[name=check_all_checklist]",
            run: "click",
        },
        {
            content: "Confirm",
            trigger: ".modal-footer .btn-primary",
            run: "click",
        },
        {
            content: "Content line is ticked and muted",
            trigger: `${field} tr.o_data_row:not(.o_is_section) td[name=name].text-muted:contains(C1)`,
        },
    ],
});
