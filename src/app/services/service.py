import re
import os

import fitz  # Biblioteca PyMuPDF
from typing import Tuple
from google import genai
from google.genai import types
from src.app.utils.question import questions
from src.app.services.tasks_storage import TaskStorage
from dotenv import load_dotenv

load_dotenv()

task_storage = TaskStorage()


class Service:
    def __init__(self):
        self.questions = questions

    def _get_section_range(self, section: str) -> Tuple[str, str]:
        parts = section.split(".")

        next_parts = parts.copy()
        next_parts[-1] = str(int(parts[-1]) + 2)
        next_section = ".".join(next_parts)

        if len(parts) > 1:
            prev_parts = parts.copy()
            if int(parts[-1]) > 0:
                prev_parts[-1] = str(int(parts[-1]) - 1)
                prev_section = ".".join(prev_parts)
            else:
                prev_section = ".".join(parts[:-1])
        else:
            prev_section = section

        return prev_section, next_section

    def _extract_section_range(
        self, full_text: str, start_section: str, end_section: str
    ) -> str:
        pages = full_text.split("---  PÁGINA ")

        start_page = None
        for index, page in enumerate(pages):
            if f"{start_section} " in page and ("Índice" in page or index < 5):
                pattern = rf"{re.escape(start_section)}\s+([^\n]+)\s*(\d+)"
                match = re.search(pattern, page)
                if match:
                    start_page = int(match.group(2))
                    break

        end_page = None
        for index, page in enumerate(pages):
            if f"{end_section} " in page and ("Índice" in page or index < 5):
                pattern = rf"{re.escape(end_section)}\s+([^\n]+)\s*(\d+)"
                match = re.search(pattern, page)
                if match:
                    end_page = int(match.group(2))
                    break

        if not start_page:
            return ""

        if not end_page:
            end_page = start_page + 10

        extracted_content = []
        for index, page in enumerate(pages):
            for page_num in range(start_page, end_page + 1):
                if f" {page_num}" in page or f"PÁGINA: {page_num}" in page:
                    lines = page.split("\n")
                    cleared_lines = []

                    for line in lines:
                        cleared_line = line.strip()
                        if (
                            cleared_line
                            and "PÁGINA:" not in cleared_line
                            and "Formulário de Referência" not in cleared_line
                            and "Versão" not in cleared_line
                            and not cleared_line.isdigit()
                            and len(cleared_line) > 2
                            and "--- PÁGINA" not in cleared_line
                        ):
                            cleared_lines.append(line)

                    if cleared_lines:
                        extracted_content.extend(cleared_lines)
                    break

        full_content = "\n".join(extracted_content)
        full_content = re.sub(r"\n\s*\n\s*\n+", "\n\n", full_content)
        return full_content.strip()

    def _section_extract(self, full_text: str, target_section: str) -> str:
        pages = full_text.split("---  PÁGINA ")

        index_page = None
        section_number_page = None

        for index, page in enumerate(pages):
            if f"{target_section} " in page and ("Índice" in page or index < 5):
                pattern = rf"{re.escape(target_section)}\s+([^\n]+)\s*(\d+)"
                match = re.search(pattern, page)
                if match:
                    section_number_page = int(match.group(2))
                    index_page = index
                    break

        if section_number_page is None:
            print(f"⚠️  Seção {target_section} não encontrada. Tentando fallback...")
            prev_section, next_section = self._get_section_range(target_section)
            fallback_content = self._extract_section_range(
                full_text, prev_section, next_section
            )

            if fallback_content:
                print(
                    f"✓ Fallback bem-sucedido: extraindo de {prev_section} até {next_section}"
                )
                return fallback_content
            else:
                print(f"✗ Fallback falhou para seção {target_section}")
                return f"Erro: A seção com o número '{target_section}' não foi encontrada no índice do documento."

        full_title = None
        searched_content = ""

        for index, page in enumerate(pages):
            if (
                f" {section_number_page}" in page
                or f"PÁGINA: {section_number_page}" in page
            ):
                pattern_section = (
                    rf"^{re.escape(target_section)}\s+([A-Za-zÀ-ÿ].{{10,}}.*?)$"
                )

                match_section = re.search(pattern_section, page, re.MULTILINE)

                if match_section:
                    full_title = match_section.group(0).strip()

                    content_start = match_section.end()
                    page_content = page[content_start:]

                    lines = page_content.split("\n")
                    cleared_lines = []

                    for line in lines:
                        cleared_line = line.strip()
                        if (
                            cleared_line
                            and "PÁGINA:" not in cleared_line
                            and "Formulário de Referência" not in cleared_line
                            and "Versão" not in cleared_line
                            and not cleared_line.isdigit()
                            and len(cleared_line) > 2
                        ):
                            cleared_lines.append(line)

                    searched_content = "\n".join(cleared_lines)
                    break

        if not full_title:
            return f"Erro: Não foi possível encontrar o conteúdo da seção '{section_number_page}' na página indicada."

        current_level = len(target_section.split("."))

        next_section_number = None
        next_section_page = None

        if index_page is not None:
            page_index_text = pages[index_page]

            pattern_all_sections = r"(\d+(?:\.\d+)*)\s+([^\n]+)\s*(\d+)"
            full_sections = re.findall(pattern_all_sections, page_index_text)

            current_section_found = False
            for number, title, number_page in full_sections:
                if current_section_found:
                    section_level = len(number.split("."))
                    if section_level <= current_level:
                        next_section_number = number
                        next_section_page = int(number_page)
                        break
                elif number == target_section:
                    current_section_found = True

        if next_section_page:
            page_to_extract = range(section_number_page, next_section_page)
        else:
            page_to_extract = range(section_number_page, section_number_page + 10)

        extra_content = []

        for index, page in enumerate(pages):
            for target_page in page_to_extract:
                if f"{target_page} " in page or f"PÁGINA: {target_page}" in page:
                    if target_page > section_number_page:
                        if next_section_number:
                            next_pattern = rf"^{re.escape(next_section_number)}\s+"
                            if re.search(next_pattern, page, re.MULTILINE):
                                break

                        lines = page.split("\n")
                        cleared_lines = []

                        for line in lines:
                            cleared_line = line.strip()
                            if (
                                cleared_line
                                and "PÁGINA:" not in cleared_line
                                and "Formulário de Referência" not in cleared_line
                                and "Versão" not in cleared_line
                                and not cleared_line.isdigit()
                                and len(cleared_line) > 2
                                and f"--- PÁGINA {target_page}" not in cleared_line
                            ):
                                cleared_lines.append(line)

                        if cleared_lines:
                            extra_content.extend(cleared_lines)
                    break

        full_content = searched_content
        if extra_content:
            full_content += "\n" + "\n".join(extra_content)

        full_content = re.sub(r"\n\s*\n\s*\n+", "\n\n", full_content)
        full_content = full_content.strip()

        return full_content

    def key_choice(self, question_number: int):
        """Escolhe a chave baseada no número da questão"""
        if question_number <= 6:
            key = os.environ.get("GEMINI_KEY_1")
        elif 6 < question_number <= 12:
            key = os.environ.get("GEMINI_KEY_2")
        elif 12 < question_number <= 18:
            key = os.environ.get("GEMINI_KEY_3")
        else:
            key = os.environ.get("GEMINI_KEY_4")

        if not key:
            raise ValueError(
                f"Chave não configurada para questão #{question_number}. Verifique as variáveis de ambiente GEMINI_KEY_*"
            )

        return key

    async def _get_answer(
        self, doc_path: str, prompt: str, question_number: int
    ) -> str:
        client = genai.Client(api_key=self.key_choice(question_number))

        with open(doc_path, "r", encoding="utf-8") as file:
            doc_data = file.read().encode("utf-8")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=doc_data,
                    mime_type="text/plain",
                ),
                prompt,
            ],
        )

        return response.text

    async def extract_response(self, path_file: str, task_id=None):
        if task_id:
            task_storage.update_task(task_id, status="processing")

        try:
            full_text = ""
            with fitz.open(path_file) as doc:
                for page_number, page in enumerate(doc):
                    page_text = page.get_text("text")
                    full_text += f"\n---  PÁGINA {page_number + 1} ---\n" + page_text
        except FileNotFoundError:
            error_msg = "Arquivo não encontrado."
            if task_id:
                task_storage.fail_task(task_id, error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Erro ao ler o arquivo: {str(e)}"
            if task_id:
                task_storage.fail_task(task_id, error_msg)
            return error_msg

        sheet_answers = {}
        last_sections = []
        all_contents = []

        total_questions = len(self.questions)

        if task_id:
            task_storage.set_progress(task_id, 0, total_questions)

        for index, question in enumerate(self.questions):
            try:
                section_numbers = question.get("Onde")
                question_text = question.get("Questao")
                how_to_fill = question.get("ComoPreencher")
                observations = question.get("OBSERVACOES")
                question_number = question.get("Nº")

                if task_id:
                    task_storage.set_progress(task_id, index + 1, total_questions)
                    print(f"📊 Processando questão {index + 1}/{total_questions}")

                if section_numbers != last_sections:
                    all_contents = []
                    for section_number in section_numbers:
                        content = self._section_extract(full_text, section_number)
                        all_contents.append(content)
                    last_sections = section_numbers

                full_content = "\n\n".join(all_contents)

                try:
                    with open("extracted_section.txt", "w", encoding="utf-8") as file:
                        file.write(full_content)
                    print(f"\n✓ Seções extraídas para questão {index + 1}")
                except Exception as e:
                    error_msg = f"Erro ao salvar o arquivo: {str(e)}"
                    if task_id:
                        task_storage.fail_task(task_id, error_msg)
                    return error_msg

                prompt = f"""
                {question_text}

                Retorne apenas como é pedido aqui:{how_to_fill}

                {observations}
                """
                answer = await self._get_answer(
                    "extracted_section.txt", prompt, question_number=question_number
                )

                sheet_answers[question_text] = answer
                print(f"✓ Questão {index + 1} respondida")

            except Exception as e:
                error_msg = f"Erro na questão {index + 1}: {str(e)}"
                print(f"❌ {error_msg}")
                sheet_answers[question_text] = f"ERRO: {str(e)}"

        if task_id:
            task_storage.complete_task(task_id, sheet_answers)
            print(f"✅ Processamento completo! Task ID: {task_id}")

        return sheet_answers
