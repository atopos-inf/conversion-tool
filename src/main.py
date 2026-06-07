import gradio as gr
import html
import re

def split_chapters(content): 
    chapter_pattern = re.compile(r'(?m)^(第(?:[零一二三四五六七八九十百0-9]+)章[^\r\n]*)')   #正则表达式匹配章节标题
    matches = list(chapter_pattern.finditer(content))         #查找所有符合章节标题格式的位置,存入matches列表

    if not matches:
        return [], []
    
    #提取章节前的内容（如有）
    before_text = content[: matches[0].start()].strip()
    before_sections = [before_text] if before_text else []
    
    #提取章节内容
    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        chapter_block = content[start:end].strip()
        title = match.group(1).strip()
        body = chapter_block[len(title) :].strip()
        chapters.append({
            'title': title,
            'content': body,
        })

    return before_sections, chapters

def process_file(file_path):  # gradio file_upload组件upload事件处理方法
    #上传文件检查
    file_ext=file_path.split('.')[-1].lower()   
    if file_ext not in ['txt']:
        return '请上传txt格式文件',None
    #文件加载预处理
    if file_ext=='txt':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return f'文件读取失败：{e}', '', ''
        
    before_sections, chapters = split_chapters(content)

    # 将章节内容渲染为 HTML 预览
    if chapters:
        parts = []
        for ch in chapters:
            title = html.escape(ch.get('title', ''))
            body = html.escape(ch.get('content', ''))
            parts.append(f'<h3 style="margin:8px 0 4px 0; font-size:1rem;">{title}</h3>')
            parts.append(f'<pre style="white-space: pre-wrap; word-break: break-word; margin:0 0 12px 0;">{body}</pre>')
        body_html = ''.join(parts)
    else:
        body_html = f'<pre style="white-space: pre-wrap; word-break: break-word; margin: 0;">{html.escape(content)}</pre>'

    preview_html = (
        '<h3>内容预览</h3>'
        '<div style="max-height: 400px; overflow-y: auto; padding: 12px; border: 1px solid #ddd; border-radius: 8px; background: #fafafa;">'
        + body_html +
        '</div>'
    )
    
    # 返回成功信息和数据预览
    return '文件已成功加载', preview_html

with gr.Blocks() as demo:
    gr.Markdown("# 智能剧本创作助手")

    
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="上传小说文件 (现仅支持txt格式)")
            upload_output = gr.Textbox(label="上传状态")
            data_preview = gr.HTML(label="内容预览" )

            
    # 文件上传事件处理
    file_input.upload(
        fn=process_file,
        inputs=[file_input],
        outputs=[upload_output, data_preview]
    )

demo.launch()