# 📄 AUP_pdf_tool — 74-in-1 PDF & CSC e-Services Suite (Streamlit)

An all-in-one Streamlit web application built for **AUP E-Services**, combining **74 PDF, Image, Office, eBook, and CSC Pro tools** in a single clean interface ready for **GitHub + Streamlit Community Cloud** deployment.

## Included Tools (74 Total)

- **CSC & Pro Tools (7):** Compress PDF to Target KB (100/200/300/500 KB), ID Card Front & Back to Single-Page A4 PDF, OCR PDF (Tamil + English), Sign & Seal PDF, Grayscale (B&W) PDF, HTML / URL to PDF, Repair & Flatten PDF
- **Core PDF (12):** Compress PDF (Slider), Merge PDF, Merge PDF and Image, Split PDF, Crop PDF, Organize PDF, Rotate PDF, Remove Pages, Extract Pages from PDF, Extract Images from PDF, Add Page Number, Add Watermark
- **Images & PDF (9):** Image to PDF, PDF to Image, JPG to PDF, PDF to JPG, AVIF to PDF, HEIC to PDF, HEIF to PDF, TIFF to PDF, JFIF to PDF
- **Security & Text (4):** TXT to PDF, PDF to Text, Unlock PDF, Protect PDF
- **Office & PDF (24):** Word/DOC/DOCM/PowerPoint/PPT/PPSX/Excel/XLS/ODT/ODS/ODP/WPS/PAGES/HWP/CSV to PDF, and PDF to Word/DOC/PowerPoint/PPT/Excel/XLS/ODT/ODP/CSV
- **eBooks & PDF (18):** eBook/EPUB/MOBI/AZW/AZW3/DJVU/CBZ/CBR/FB2/RTF/CHM/LIT to PDF, and PDF to eBook/EPUB/MOBI/AZW3/FB2/RTF

## Deploy to Streamlit Community Cloud (Recommended)

1. Unzip `AUP_pdf_tool.zip` on your computer.
2. Create a new GitHub repository named **`AUP_pdf_tool`**.
3. Push the folder contents to GitHub:
   ```bash
   cd AUP_pdf_tool
   git init
   git add .
   git commit -m "Initial commit: AUP_pdf_tool 74-in-1 PDF suite"
   git branch -M main
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/AUP_pdf_tool.git
   git push -u origin main
   ```
4. Go to **https://share.streamlit.io**, click **New app**, select your `AUP_pdf_tool` repo, branch `main`, main file path `app.py`, and click **Deploy**.
5. Streamlit Cloud automatically installs both `packages.txt` (LibreOffice, Calibre, Ghostscript, Tesseract OCR Tamil+English, QPDF, DjVuLibre, Poppler, 7z) and `requirements.txt` (Python libraries).

## Run Locally (Windows / Linux / macOS)

```bash
cd AUP_pdf_tool
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```
