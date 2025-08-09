import os
import shutil
from fpdf import FPDF
import pypandoc

input_dir = '/Users/zachklopping/Desktop/List 25/Paper Outputs/Raw_read_me'
output_dir = '/Users/zachklopping/Desktop/List 25/Paper Outputs/Read Me/AER_pdf 2'
os.makedirs(output_dir, exist_ok=True)

document_exts = {
    ".doc", ".docx", ".odt", ".rtf", ".rtf-", ".txt", ".md", ".html",
    ".xlsx", ".lyx", ".lyx-", ".tex", ".rmd", ".rst"
}

for filename in os.listdir(input_dir):
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    input_path = os.path.join(input_dir, filename)
    output_path = os.path.join(output_dir, f"{name}.pdf")

    try:
        # COPY PDFS
        if ext == ".pdf":
            shutil.copy2(input_path, output_path)
            print(f"Copied {filename}")

        # TXT to PDF
        elif ext == ".txt":
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            with open(input_path, 'r', encoding='utf-8') as file:
                for line in file:
                    pdf.cell(0, 10, txt=line.strip(), ln=True)
            pdf.output(output_path)
            print(f"Converted {filename}")

        # DOCX, ODT, RTF, MD, HTML, RMD, RST, TEX, LYX, LYX- using Pandoc (if installed)
        elif ext in {".docx", ".odt", ".rtf", ".md", ".html", ".rmd", ".rst", ".tex", ".lyx", ".lyx-"}:
            pypandoc.convert_file(input_path, "pdf", outputfile=output_path)
            print(f"Converted {filename}")

        # DOC (old Word format) using Pandoc (may need antiword installed for .doc)
        elif ext == ".doc":
            pypandoc.convert_file(input_path, "pdf", outputfile=output_path)
            print(f"Converted {filename}")

        else:
            print(f"Skipped {filename} (not a readable doc)")

    except Exception as e:
        print(f"Error with {filename}: {e}")

print("Done!")
