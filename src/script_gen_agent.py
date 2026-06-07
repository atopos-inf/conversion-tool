import os
import re
import html
from pathlib import Path
from dotenv import load_dotenv

from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 加载 .env：优先从脚本所在目录加载
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Agent:
    """AI 辅助剧本创作工具的核心 Agent 类"""

    def __init__(self):
        self.llm = None
        self.extract_chain = None
        self.merge_chain = None
        self.chapters = []
        self.extracted_elems = []

    def split_chapters(self, content):
        """将小说内容按章节分割"""
        chapter_pattern = re.compile(
            r'(?m)^(第(?:[零一二三四五六七八九十百0-9]+)章[^\r\n]*)'
        )
        matches = list(chapter_pattern.finditer(content))

        if not matches:
            return [], []

        # 提取章节前的内容（如有）
        before_text = content[: matches[0].start()].strip()
        before_sections = [before_text] if before_text else []

        # 提取章节内容
        chapters = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            chapter_block = content[start:end].strip()
            title = match.group(1).strip()
            body = chapter_block[len(title):].strip()
            chapters.append({
                'title': title,
                'content': body,
            })

        return before_sections, chapters

    def process_file(self, file_path):
        """处理上传的文件 - Gradio file_upload 组件 upload 事件处理方法"""
        # 上传文件检查
        if isinstance(file_path, str):
            file_ext = file_path.split('.')[-1].lower()
        else:
            return '请上传有效的文件路径', None

        if file_ext not in ['txt']:
            return '请上传txt格式文件', None

        # 文件加载预处理
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return f'文件读取失败：{e}', None

        before_sections, chapters = self.split_chapters(content)
        self.chapters = chapters

        # 将章节内容渲染为 HTML 预览
        if chapters:
            parts = []
            for ch in chapters:
                title = html.escape(ch.get('title', ''))
                body = html.escape(ch.get('content', ''))
                parts.append(
                    f'<h3 style="margin:8px 0 4px 0; font-size:1rem;">{title}</h3>'
                )
                parts.append(
                    f'<pre style="white-space: pre-wrap; word-break: break-word; margin:0 0 12px 0;">{body}</pre>'
                )
            body_html = ''.join(parts)
            chapter_count = len(chapters)
            status_msg = f'文件已成功加载，共识别 {chapter_count} 章'
        else:
            body_html = f'<pre style="white-space: pre-wrap; word-break: break-word; margin: 0;">{html.escape(content)}</pre>'
            status_msg = '文件已加载，但未识别到章节标题'

        preview_html = (
            '<h3>内容预览</h3>'
            '<div style="max-height: 400px; overflow-y: auto; padding: 12px; '
            'border: 1px solid #ddd; border-radius: 8px; background: #fafafa;">'
            + body_html +
            '</div>'
        )

        # 初始化 agent
        self.create_agent()

        return status_msg, preview_html

    def create_agent(self):
        """初始化 LLM 并创建处理链"""
        # 初始化 DeepSeek LLM
        self.llm = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=4096,
        )

        # ========== 元素提取 Prompt ==========
        extract_system_prompt = """你是一个专业的剧本元素提取与连续性追踪专家。
请严格按照 SCRIPT_YAML_SCHEMA.md 的格式，将小说章节内容转换为结构化剧本元素。

要求：
1. 提取当前文本中的所有对白、动作、表情描写、环境氛围。
2. 识别并记录所有出现的角色及其别名。
3. 判断是否有**未完成的元素**（如对白没有闭合引号、动作描述在结尾处中断）。
4. 如果有未完成元素，在输出的最后用 `continuity:` 字段标记出来，以便下一块继续处理。
5. 按场景为单位组织内容，每个场景包含 location、time、mood 等信息。

请仅返回符合 schema 的 YAML 文本，不要包含任何多余的解释。"""

        self.extract_prompt = ChatPromptTemplate.from_messages([
            ("system", extract_system_prompt),
            ("human", "## 当前章节内容\n\n{chapter_content}\n\n"
                      "## 连续性上下文（上一章节未完成元素）\n\n{continuity_context}\n\n"
                      "请提取以上内容的剧本元素，并以 YAML 格式输出。"),
        ])

        self.extract_chain = self.extract_prompt | self.llm | StrOutputParser()

        # ========== 剧本合并 Prompt ==========
        merge_system_prompt = """你是一个专业的剧本整合专家。
请将多个章节提取的剧本元素合并为一个完整的、连续的剧本 YAML。

要求：
1. 统一**所有角色名称**，消除别名冲突（同一角色不同称呼合并为统一 ID）。
2. 生成完整的 `metadata` 部分（标题可从小说名推断，其他字段根据内容合理补充）。
3. 生成完整的 `characters` 角色清单。
4. 按章节顺序排列所有 `scenes`，确保场景 ID 连续。
5. 处理章节间的连续性（如未完成的对白、动作在下一章节继续）。
6. 严格按照 SCRIPT_YAML_SCHEMA.md 格式输出。
7. 最终输出必须是一个完整的、可解析的 YAML 文档。"""

        self.merge_prompt = ChatPromptTemplate.from_messages([
            ("system", merge_system_prompt),
            ("human", "以下是各章节提取的剧本元素，请合并为一个完整的剧本：\n\n"
                      "{all_extracts}\n\n请仅返回完整的 YAML 剧本内容。"),
        ])

        self.merge_chain = self.merge_prompt | self.llm | StrOutputParser()

    def _extract_continuity(self, response_text: str) -> str:
        """从 agent 返回中提取连续性上下文"""
        continuity_match = re.search(
            r'continuity[:\s]+(.*?)(?:\n\S|$)',
            response_text,
            re.DOTALL
        )
        if continuity_match:
            return continuity_match.group(1).strip()
        return ""

    def elem_extract(self, chapters):
        """顺序处理每个章节并调用 agent 提取元素"""
        if not chapters:
            return []

        responses = []
        continuity_context = "无"

        for idx, ch in enumerate(chapters):
            print(f"正在处理第 {idx + 1}/{len(chapters)} 章: {ch['title']}")

            response = self.extract_chain.invoke({
                "chapter_content": ch['content'],
                "continuity_context": continuity_context
            })

            # 提取连续性上下文供下一章节使用
            continuity_context = self._extract_continuity(response)
            if not continuity_context:
                continuity_context = "无"

            responses.append({
                'index': idx,
                'title': ch['title'],
                'response': response
            })

        return responses

    def generate_script(self):
        """生成最终完整剧本"""
        if not self.chapters:
            return "请先上传小说文件"

        if not self.extracted_elems:
            self.extracted_elems = self.elem_extract(self.chapters)

        # 合并所有章节的提取结果
        all_extracts = "\n\n---\n\n".join(
            [item['response'] for item in self.extracted_elems]
        )

        if not all_extracts.strip():
            return "章节提取结果为空，请检查小说内容"

        print("正在合并生成最终剧本...")
        final_script = self.merge_chain.invoke({
            "all_extracts": all_extracts
        })

        return final_script


if __name__ == "__main__":
    da = Agent()
    status, preview = da.process_file('我老婆是东晋第一女魔头(1-500章).txt')
    print(status)

    # 顺序提取章节元素（示例：仅前 3 章）
    elems = da.elem_extract(da.chapters[:3])
    for item in elems:
        print(f"== 第{item['index'] + 1}章: {item['title']} ==")
        print(item['response'][:200])
        print("...")
