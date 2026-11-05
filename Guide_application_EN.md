# Album Photos application guide (English)

Version of 01/11/2026. One window gathers every step of the photo book and of the photo-letters poster. Each button does exactly what the `.bat` file of the same name does; the `.bat` files still work.

**Safety rule:** the application only **reads** your photos. It never changes, moves or deletes anything on the backup drive. Everything it creates goes into the work folder, for example `C:\AlbumsFamille`.

**Language:** the **🌐 EN / FR** button at the top right switches the application language. The language of the book itself is set in Settings > Book > "Language of the book and letters poster" (`fr` or `en`). Detailed log messages stay in French.

## 1. Install the application (once)

| Step | What to do |
|---|---|
| 1. Python | If Python is not installed yet: https://www.python.org/downloads/. On the first screen tick **"Add python.exe to PATH"**, then restart the PC. |
| 2. The tool | Unzip the zip you received (e.g. in Documents). The tool's author uses their Git copy `%USERPROFILE%\AlbumPhotos\outils\albums-famille`. |
| 3. Install | In that folder, double-click **`Installer_application.bat`**. It installs the libraries (a few minutes the first time), creates the **Album Photos** icon on the Desktop and in the Start menu, then opens the application. |
| 4. Afterwards | Simply open **Album Photos** from the Desktop. |

### Check the tool (automatic tests)

The **🔧 Maintenance** > **Check the tool (tests)** button (or `9_tests_automatiques.bat`) runs 39 tests in 1 to 3 minutes on a small disk of **synthetic photos** created in a temporary folder: your photos, settings and books are not used. They cover analysis, selection, previews, final book with PowerPoint, letters poster, browser screens (security token), suggestions, translation, settings (multi-line letter, safe writing) and above all that **original photos are never modified**. At the end, "OK" and "Tous les tests sont passés" appear in green; otherwise send `journal.txt` to Claude.

## 2. The screen

| Area | Role |
|---|---|
| Top bar | Name of the book's person, folders in use, version. On the right: running step, activity bar, **■ Stop the step** button, **🌐 EN / FR** button. |
| Left column | The step buttons, in order (1 to 5; setup and updates are in **🔧 Maintenance**): **blue ▶ buttons**; **the recommended one is green**. While a step runs, the others are greyed out. Below, the white "Open" buttons open the folders. |
| **Log** tab | What the step is doing, live. The green line at the top gives the recommended next step. Errors are in red. |
| **Settings** tab | All settings, on three pages: Photos and people, Book, Letters poster. Each setting is in a white box: a bold title, the field to fill in (blue border while typing, ▼ arrow for a list) and grey help text. Green **✔ Save the settings** button at the top (saving is also automatic before each step). |
| **Help** tab | This guide. |

## 3. Making the book step by step

| No. | Button | What happens |
|---|---|---|
| 0 | **Settings** tab | Fill in at least: photo folder ("Browse…"), work folder, person of the book, close relatives, date of birth, "home" countries (FR,PH). |
| 1 | **🔧 Maintenance** > **Install / repair** | Checks the libraries and creates one reference photo folder per person. |
| — | **Reference photos** (Open) | Put 3 to 10 sharp photos of each person's face in their folder, at different ages, baby included. |
| 2 | **Analyse the drive** | Reads all photos (dates, places, faces, sharpness). Can be stopped and restarted: work already done is kept. Several hours the first time. |
| 3 | **Prepare the selection** | Suggests the book photos, grouped into memories. |
| 3a | **Choose the photos** | The browser opens: one click keeps / removes a photo, 🔍 enlarges it. Filter buttons: **★ Special**, **★ Cover**, **★ Full page**, **✉ Letters**, **◆ Master**, **Set aside**, with their counts. Finish with **Terminer** on the page. |
| 3b | **Reduce the selection** *(optional)* | Kept photos only, with the best candidates for removal flagged. |
| 3c | **Suggest improvements** *(optional)* | A screen opens: each suggestion (replace, add, remove) with its photos; **one click accepts or refuses it**, "Accept all" / "Refuse all", then **"Apply the choices"** updates the selection (backup copy made). No more Excel. "Review the suggestions" reopens this screen without recomputing. |
| 4 | **Style previews** | A window lets you **tick the styles to make or redo**; unticked previews stay as they are. One preview PDF per style in the book folder. |
| — | Settings > Book | Choose the **style**; if you wish, the number of pages, organisation, language, footer, end text, dedication. |
| 5 | **Final book** | The book + the printer folder: PDF, photos numbered in order, Excel instructions, assembly plan. |
| 5b | **Book + editable PowerPoint** *(optional)* | Same, plus a `.pptx` file to retouch a page by hand. |

### Book options (Settings > Book)

| Setting | Example | Effect |
|---|---|---|
| Language of the book | `en` | Titles, dates, ages, countries, bubbles and fixed pages in English. Hand-typed captions and titles stay as typed. |
| Footer | `Laura · 2012-2024` | Small text at the bottom of the pages, on the outer side. |
| Pages with the footer | `photos-uniques` | `toutes` = every page after the first; `photos-uniques` = only pages with a single photo. |
| Text at the end of the album | a multi-paragraph letter | Large text box in the application, saved in `texte_fin.txt`. Line breaks and paragraphs are kept, the size adapts so everything fits (never cut), a short first line ("My darling,") becomes a heading. A ❤️ becomes a drawn heart. |
| Symbol above the end text | `coeurs` | coeurs, coeur, fleur, ornement, colombe, etoiles or aucun: drawn in the application; click a drawing to choose it. |
| Caption box colour (comic styles) | `vert` | yellow (default), blue, dark blue, green, pink, orange, red, purple… or `#RRGGBB`. |

### Comic styles: bubbles and caption boxes

The bubble ("Happy birthday!") and the caption box go where there is no face, with a smaller font if needed (down to 9 pt). If no free spot exists, there is no bubble. If the photo is reduced (quality), the caption box goes in the free space next to it.

### Checks shown in the previews only

* orange label: photo reduced to stay sharp when printed;
* red label: a face is already cut off in the original photo (no crop can fix it: replace the photo if possible).
Both are listed on the last page of the preview.

### Improving face recognition

| Problem | What to do |
|---|---|
| Photos kept **without the person** | **Check the recognition** button: faces given to the person, **least sure first**. **✗ Not Laura** forbids it for good, **✓ It's Laura** adds a reference at that exact age. Then run **Prepare the selection** again. |
| A photo **without the person** in the choice screen | Hover it and click **✗ Not Laura** (or key **N** when enlarged): removed from the book **and** never suggested again. Each refusal also teaches the tool to reject look-alike faces. |
| **Start from scratch** | **Check the recognition** screen > **Erase all my corrections**, then **Prepare the selection** (answer "o": the selection is rebuilt entirely). |
| **Missed** photos | Same screen, "Maybe Laura" list: one ✓ click. |
| Many errors | Settings > "Face likeness requirement": 0.45 or 0.50. |
| Reference photos | 10 to 20 per person, **one per period**, large sharp frontal face, **alone or clearly in front**. Photos with several same-size faces, or unlike the others, are discarded automatically (see the log). |

### Making another person's book (Bo, Hugo…)

**The drive analysis is done once for the whole family.** It detects faces and computes their fingerprints, but does not yet know who is who. Recognising the book's person happens at "Prepare the selection", by comparing faces with the reference photos.

| For a new book | To do |
|---|---|
| 1 | Settings > "Person of the book": the new name (and close relatives) |
| 2 | **Reference photos**: 3 to 10 sharp photos of their face in `famille\<Name>` |
| 3 | **Prepare the selection**, then the usual steps |
| ✗ | **No need to rerun "Analyse the drive"**: only if you add photos to the drive (only new ones are analysed). The application reminds you if you click it. |

Each person has their own `livre_<Name>` folder: books never mix.

## 4. The photo-letters poster

| No. | Where | What to do |
|---|---|---|
| 1 | Settings > Letters poster | Word, texts above and below, format, designs, colours. |
| 2 | **Choose the letter photos** | The browser opens: click one photo per letter (placed by date). The book selection is not changed. |
| 3 | **Create the letters poster** | The designs as 300 dpi JPEG + PDF, plus `Comparaison_modeles.jpg`. |
| 4 | **Letter posters** (Open) | Choose the design for the printer. |

**Schematic preview:** in Settings > Letters poster, the poster is drawn live next to the settings (format, background, font, outline, colours, one or two lines, texts; coloured letters stand for the photos). The "Designs to make" list just above sets both what is shown and what will be made: one design, or "all" (the 6 as thumbnails). In English, every drop-down list (colours, formats, styles, symbols…) and the photo selection screens in the browser are in English too; the settings file always keeps the same codes.

To put the poster on the first page of the book: Settings > Letters poster > "Put the poster in the photo book" = `premiere-page` (or `premiere-et-derniere`).

## 4b. The photo mosaic

A "master" photo (a portrait, for example) rebuilt from hundreds of small album photos: from afar you see the face, up close every memory.

| No. | Where | What to do |
|---|---|---|
| 1 | **Choose the photos** | Enlarge a photo (🔍) then **◆ Master**: it becomes the photo to rebuild (the book selection is unchanged). Or: Settings > Mosaic > "Master photo" > Browse… Without a choice: the cover. |
| 2 | Settings > Mosaic | Format **A4 to A0**, small photos across (60; 80 to 120 for A0), master blended on top (0.35), "kept" or "all" photos, or a **thumbnail photos folder** (Settings > Mosaic, optional; never changed). Empty = the album's selected photos; filled = the small photos come from that folder; "kept + folder" = both. |
| 2b | **Mosaic preview** (or "↻ Refresh the preview" in Settings > Mosaic) | Quick render in a few seconds with the current settings, shown next to the settings: try formats, photo counts and blends before making the poster. |
| 3 | **Create the mosaic** | `livre_<Name>\mosaique`: the large JPEG for the printer, a preview, a close-up detail and the list of photos used. |

Advanced settings: face rendering (adaptive = more detail on eyes and mouth), small photos tint, line between photos, gap between identical photos, bleed (3 mm), and **text on the photo** ("|" = new line; position auto/top/bottom/centre/corners, font, colour, size, style shadow/outline/band). Printer files: maximum-quality JPEG with sRGB profile and a PDF at the exact size.

Quality: 300 dpi up to A2, 200 dpi for A1, 150 dpi for A0 (poster standard). At least 150 photos recommended.

## 5. Maintenance, updating and sharing

The **🔧 Maintenance** button (top right) opens a window with **Install / repair** and **Check the tool (tests)** for everyone, and, **for the administrator only**, **Update the tool** (from GitHub) and **Make the zip to share** (a clean copy without your settings, data or GitHub link, in the work folder). Administrator mode is automatic on the author's Git copy, or with an empty `admin.txt` file next to the application. A shared copy has no GitHub button and cannot update itself.

Administrator: click **Update the tool**: the application downloads the latest version, then offers to restart. Your settings, selections and books are never touched. Libraries are reinstalled only when their list has changed (faster updates).

Note: after an update that changes how photos are framed, the first preview takes longer (every crop is redone). The next ones are fast again.

## 6. Troubleshooting

| Problem | Solution |
|---|---|
| The icon does nothing | Double-click `Lancer_application.bat`. If Python is not found, reinstall it with "Add python.exe to PATH" ticked, then run `Installer_application.bat` again. |
| "Libraries to install" | **🔧 Maintenance** > **Install / repair**. |
| Photo folder not found | Plug in the backup drive; if its letter changed (D:, E:…), fix the path in Settings. |
| A step seems stuck | The bar moves as long as it works. For selection screens, finish with **Terminer** in the browser. Otherwise **■ Stop the step**. |
| A red error | Click **journal.txt** (Open) and send that file to Claude. |
