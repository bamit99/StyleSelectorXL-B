import contextlib
import gradio as gr
from modules import scripts, shared, script_callbacks
from modules.ui_components import FormRow, FormColumn, FormGroup, ToolButton
import json
import os
import random

class StyleSelectorXL(scripts.Script):
    def __init__(self) -> None:
        super().__init__()
        self.json_files = self.get_json_files()
        self.selected_file = self.json_files[0] if self.json_files else None
        self.styleNames = self.getStyles(self.selected_file)

    @classmethod
    def get_json_files(cls):
        script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        json_files = [f for f in os.listdir(script_dir) if f.endswith('.json')]
        return json_files

    @staticmethod
    def get_json_content(file_path):
        try:
            with open(file_path, 'rt', encoding="utf-8") as file:
                json_data = json.load(file)
                return json_data
        except Exception as e:
            print(f"A Problem occurred while reading {file_path}: {str(e)}")
            return None

    @staticmethod
    def read_sdxl_styles(json_data):
        if not isinstance(json_data, list):
            print("Error: input data must be a list")
            return []

        names = []
        for item in json_data:
            if isinstance(item, dict) and 'name' in item:
                names.append(item['name'])
        names.sort()
        return names

    def getStyles(self, selected_file):
        if not selected_file:
            return []
        script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        json_path = os.path.join(script_dir, selected_file)
        json_data = self.get_json_content(json_path)
        if json_data is None:
            return []
        return self.read_sdxl_styles(json_data)

    def createPositive(self, style, positive, selected_file):
        script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        json_path = os.path.join(script_dir, selected_file)
        json_data = self.get_json_content(json_path)
        try:
            if not isinstance(json_data, list):
                raise ValueError("Invalid JSON data. Expected a list of templates.")

            for template in json_data:
                if 'name' not in template or 'prompt' not in template:
                    raise ValueError("Invalid template. Missing 'name' or 'prompt' field.")

                if template['name'] == style:
                    positive = template['prompt'].replace('{prompt}', positive)
                    return positive

            raise ValueError(f"No template found with name '{style}'.")

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return positive  # Return original prompt if there's an error

    def createNegative(self, style, negative, selected_file):
        script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        json_path = os.path.join(script_dir, selected_file)
        json_data = self.get_json_content(json_path)
        try:
            if not isinstance(json_data, list):
                raise ValueError("Invalid JSON data. Expected a list of templates.")

            for template in json_data:
                if 'name' not in template or 'prompt' not in template:
                    raise ValueError("Invalid template. Missing 'name' or 'prompt' field.")

                if template['name'] == style:
                    json_negative_prompt = template.get('negative_prompt', "")
                    if negative:
                        negative = f"{json_negative_prompt}, {negative}" if json_negative_prompt else negative
                    else:
                        negative = json_negative_prompt

                    return negative

            raise ValueError(f"No template found with name '{style}'.")

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return negative  # Return original negative prompt if there's an error

    def title(self):
        return "Style Selector for SDXL 1.0"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        enabled = getattr(shared.opts, "enable_styleselector_by_default", True)
        with gr.Group():
            with gr.Accordion("SDXL Styles", open=enabled):
                with FormRow():
                    with FormColumn(min_width=160):
                        is_enabled = gr.Checkbox(value=enabled, label="Enable Style Selector", info="Enable Or Disable Style Selector")
                    with FormColumn(elem_id="Randomize Style"):
                        randomize = gr.Checkbox(value=False, label="Randomize Style", info="This Will Override Selected Style")
                    with FormColumn(elem_id="Randomize For Each Iteration"):
                        randomizeEach = gr.Checkbox(value=False, label="Randomize For Each Iteration", info="Every prompt in Batch Will Have Random Style")

                with FormRow():
                    with FormColumn(min_width=160):
                        style_count = len(self.styleNames) if self.styleNames else 0
                        allstyles = gr.Checkbox(value=False, label="Generate All Styles In Order", 
                                                info=f"To Generate Your Prompt in All Available Styles, It's Better to set batch count to {style_count} (Style Count)")

                with FormRow():
                    file_selector = gr.Dropdown(choices=self.json_files, value=self.selected_file, label="Select Style File")
                    refresh_button = ToolButton(value="\U0001f504")  # Unicode for 🔄

                style_ui_type = shared.opts.data.get("styles_ui", "radio-buttons")

                if style_ui_type == "select-list":
                    style = gr.Dropdown(choices=self.styleNames, value='base' if 'base' in self.styleNames else None, multiselect=False, label="Select Style")
                else:
                    style = gr.Radio(label='Style', choices=self.styleNames, value='base' if 'base' in self.styleNames else None)

                def update_styles(file):
                    self.selected_file = file
                    self.styleNames = self.getStyles(file)
                    default_value = 'base' if 'base' in self.styleNames else (self.styleNames[0] if self.styleNames else None)
                    return gr.update(choices=self.styleNames, value=default_value)

                def refresh_files():
                    self.json_files = self.get_json_files()
                    self.selected_file = self.json_files[0] if self.json_files else None
                    self.styleNames = self.getStyles(self.selected_file)
                    default_value = 'base' if 'base' in self.styleNames else (self.styleNames[0] if self.styleNames else None)
                    return [
                        gr.update(choices=self.json_files, value=self.selected_file),
                        gr.update(choices=self.styleNames, value=default_value)
                    ]

                file_selector.change(fn=update_styles, inputs=[file_selector], outputs=[style])
                refresh_button.click(fn=refresh_files, inputs=[], outputs=[file_selector, style])

        return [is_enabled, randomize, randomizeEach, allstyles, style, file_selector]

    def process(self, p, is_enabled, randomize, randomizeEach, allstyles, style, selected_file):
        if not is_enabled or not self.styleNames:
            return

        if randomize:
            style = random.choice(self.styleNames)
        batchCount = len(p.all_prompts)

        if batchCount == 1:
            for i, prompt in enumerate(p.all_prompts):
                positivePrompt = self.createPositive(style, prompt, selected_file)
                p.all_prompts[i] = positivePrompt
            for i, prompt in enumerate(p.all_negative_prompts):
                negativePrompt = self.createNegative(style, prompt, selected_file)
                p.all_negative_prompts[i] = negativePrompt
        if batchCount > 1:
            styles = {}
            for i, prompt in enumerate(p.all_prompts):
                if randomize:
                    styles[i] = random.choice(self.styleNames)
                else:
                    styles[i] = style
                if allstyles:
                    styles[i] = self.styleNames[i % len(self.styleNames)]
            for i, prompt in enumerate(p.all_prompts):
                positivePrompt = self.createPositive(styles[i] if randomizeEach or allstyles else styles[0], prompt, selected_file)
                p.all_prompts[i] = positivePrompt
            for i, prompt in enumerate(p.all_negative_prompts):
                negativePrompt = self.createNegative(styles[i] if randomizeEach or allstyles else styles[0], prompt, selected_file)
                p.all_negative_prompts[i] = negativePrompt

        p.extra_generation_params["Style Selector Enabled"] = True
        p.extra_generation_params["Style Selector Randomize"] = randomize
        p.extra_generation_params["Style Selector Style"] = style
        p.extra_generation_params["Style Selector File"] = selected_file

    def after_component(self, component, **kwargs):
        if kwargs.get("elem_id") == "txt2img_prompt":
            self.boxx = component
        if kwargs.get("elem_id") == "img2img_prompt":
            self.boxxIMG = component

def on_ui_settings():
    section = ("styleselector", "Style Selector")
    shared.opts.add_option("styles_ui", shared.OptionInfo("radio-buttons", "How should Style Names Rendered on UI", gr.Radio, {"choices": ["radio-buttons", "select-list"]}, section=section))
    shared.opts.add_option("enable_styleselector_by_default", shared.OptionInfo(True, "enable Style Selector by default", gr.Checkbox, section=section))

script_callbacks.on_ui_settings(on_ui_settings)
