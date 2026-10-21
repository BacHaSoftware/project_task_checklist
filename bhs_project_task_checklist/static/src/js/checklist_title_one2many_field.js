/** @odoo-module */

import { t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ChkTitleListRenderer } from "./checklist_title_list_renderer";
import {
    X2ManyField,
    x2ManyField,
    x2ManyFieldProps,
} from "@web/views/fields/x2many/x2many_field";

class ChkSectionFieldOne2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: ChkTitleListRenderer,
    };
    // OWL 3: default props are declared in the props schema (no more X.defaultProps)
    props = useProps({
        ...x2ManyFieldProps,
        editable: t.string().optional("bottom"),
    });

    setup() {
        super.setup();
        this.canOpenRecord = true;
    }
}

registry.category("fields").add("checklist_title_one2many", {
    ...x2ManyField,
    component: ChkSectionFieldOne2ManyField,
    additionalClasses: [...(x2ManyField.additionalClasses || []), "o_field_one2many"],
});
