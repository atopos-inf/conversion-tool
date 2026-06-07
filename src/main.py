import gradio as gr
from script_gen_agent import Agent

app = Agent()

with gr.Blocks(title="智能剧本创作助手", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🎬 智能剧本创作助手
        **将小说自动转换为结构化剧本（YAML 格式）**
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="📄 上传小说文件（目前仅支持 .txt 格式）",
                file_types=[".txt"],
            )
            upload_status = gr.Textbox(label="📌 上传状态", interactive=False)
            generate_btn = gr.Button("🎬 生成剧本", variant="primary", size="lg")

        with gr.Column(scale=2):
            data_preview = gr.HTML(label="📖 内容预览")

    with gr.Row():
        with gr.Column():
            yaml_output = gr.Textbox(
                label="📝 最终剧本（YAML）",
                lines=20,
                max_lines=40,
                interactive=True,
                #show_copy_button=True,
            )

    # 文件上传事件处理
    file_input.upload(
        fn=app.process_file,
        inputs=[file_input],
        outputs=[upload_status, data_preview],
    )

    # 生成剧本
    generate_btn.click(
        fn=app.generate_script,
        outputs=[yaml_output],
    )

if __name__ == "__main__":
    demo.launch()
