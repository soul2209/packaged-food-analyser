# 🥗 Packaged Food Analyser

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&size=26&duration=2800&pause=900&color=7EE787&center=true&vCenter=true&width=700&lines=Know+What+You+Eat.;Decode+Every+Ingredient.;Make+Informed+Food+Choices." alt="Packaged Food Analyser"/>
</p>

<p align="center">
  <strong>Turning complex food labels into meaningful, understandable information.</strong>
</p>

<p align="center">
  An OCR-powered food label analysis system designed to help users understand packaged food ingredients, additives, and nutritional information.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-Backend-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Tesseract-OCR-7EE787?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/HTML5-Frontend-E34F26?style=for-the-badge&logo=html5&logoColor=white"/>
  <img src="https://img.shields.io/badge/CSS3-Styling-1572B6?style=for-the-badge&logo=css3&logoColor=white"/>
  <img src="https://img.shields.io/badge/JavaScript-Interactive-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black"/>
</p>

<p align="center">
  <a href="https://github.com/soul2209/packaged-food-analyser">Repository</a> •
  <a href="#-features">Features</a> •
  <a href="#-system-architecture">Architecture</a> •
  <a href="#-installation">Installation</a>
</p>

---

## 🌱 Overview

Food packaging contains valuable information about ingredients, additives, and nutritional composition. However, interpreting technical ingredient names and unfamiliar additive codes can be difficult for everyday consumers.

**Packaged Food Analyser** aims to bridge this information gap through Optical Character Recognition (OCR) and structured food reference data.

Users can provide an image of a packaged food label, extract its ingredient information, and analyse the extracted contents to make them easier to understand.

The project focuses on making food-label information more accessible through automated text extraction, ingredient identification, and reference-based analysis.

## ✨ Core Features

| Feature | Description |
|---|---|
| 📸 Image-Based Input | Accepts packaged food label images for processing. |
| 🔍 OCR Extraction | Uses Tesseract OCR to extract text from ingredient labels. |
| 🧪 Ingredient Analysis | Processes extracted ingredient information for interpretation. |
| 📚 Additive Reference | Uses structured food-additive reference information informed by WHO-related resources. |
| 🍎 Nutritional Awareness | Provides calorie-related information to support nutritional understanding. |
| 🌐 Web Interface | Presents the analysis through an HTML, CSS, and JavaScript interface. |

## ⚙️ How It Works

The application follows a straightforward image-to-information processing pipeline.

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&size=19&duration=2500&pause=1000&color=7EE787&center=true&vCenter=true&width=650&lines=01.+Upload+%E2%86%92+02.+Extract+%E2%86%92+03.+Analyse+%E2%86%92+04.+Understand" alt="Processing pipeline"/>
</p>

```text
          ┌──────────────────────┐
          │    Food Packaging    │
          │        Image         │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │     Image Input      │
          │   Upload & Handling  │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │    Tesseract OCR     │
          │    Text Extraction  │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │   Text Processing    │
          │  Ingredient Parsing  │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ Ingredient Analysis  │
          │  & Reference Lookup  │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │   Food Information   │
          │   & User Insights    │
          └──────────────────────┘
```

*Conceptual representation of the intended processing architecture.*

## 🧠 System Architecture

The project is organised around three primary processing layers:

**1. Input and Extraction Layer**
- Receives packaged food label images.
- Processes images using Tesseract OCR.
- Extracts ingredient-related text for further analysis.

**2. Analysis and Reference Layer**
- Processes the extracted text.
- Identifies ingredient and additive information.
- Uses structured reference data to support ingredient interpretation.
- Integrates calorie-related information where available.

**3. Presentation Layer**
- Displays extracted ingredient information.
- Presents analysis results in a readable format.
- Provides a web-based interface for user interaction.

## 🛠️ Technology Stack

| Technology | Role |
|---|---|
| Python | Backend processing and application logic |
| Tesseract OCR | Optical Character Recognition |
| HTML5 | Frontend structure |
| CSS3 | Interface styling |
| JavaScript | Frontend functionality |
| Food Additive Reference Data | Ingredient and additive information |
| WHO-related Resources | Reference material for food-additive information |

## 🚀 Installation

### Prerequisites

Make sure the following are available on your system:

- Python 3.x
- Tesseract OCR
- Git
- A modern web browser

### 1. Clone the Repository

```bash
git clone https://github.com/soul2209/packaged-food-analyser.git

cd packaged-food-analyser
```

### 2. Install Tesseract OCR

Download and install Tesseract OCR for your operating system.

Official repository:

https://github.com/tesseract-ocr/tesseract

Ensure that the Tesseract executable is accessible to your Python application.

### 3. Install Python Dependencies

If the project contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 4. Run the Application

Follow the configured project entry point to start the backend.

If the frontend is standalone, open its HTML entry point in a browser. If a Python server is required, launch it using the project's configured startup command.

## 🎯 Project Objectives

- Simplify the interpretation of packaged food ingredient labels.
- Explore practical applications of OCR in everyday consumer technology.
- Make food-additive reference information easier to access.
- Encourage better nutritional awareness.
- Demonstrate how image processing and structured datasets can work together in a real-world application.

## 🔮 Future Development

The project has room for expansion beyond basic ingredient extraction.

- [ ] **Advanced OCR:** Improve recognition of curved, blurred, and low-resolution packaging.
- [ ] **Ingredient Classification:** Develop more detailed ingredient identification and categorisation.
- [ ] **Additive Insights:** Expand the reference database and provide clearer explanations of additive codes.
- [ ] **Nutritional Analysis:** Extend calorie-related information and nutritional breakdowns.
- [ ] **Allergen Detection:** Identify commonly declared allergens where reliable data is available.
- [ ] **Source Transparency:** Provide references and sources for ingredient-related information.
- [ ] **Confidence Scoring:** Communicate OCR uncertainty and potential extraction errors.
- [ ] **Responsive UI:** Improve accessibility across mobile and desktop devices.

## ⚠️ Limitations & Disclaimer

Packaged Food Analyser is an informational and educational project.

- OCR accuracy depends on image quality, lighting, orientation, and label readability.
- Incorrect text extraction may affect subsequent ingredient analysis.
- Reference databases may not cover every ingredient, additive, or regional naming convention.
- Nutritional information depends on the availability and accuracy of its underlying data.

The application is not intended to provide medical or dietary diagnoses, certify food safety, or replace professional nutritional advice.

## 👨‍💻 Developer

**Dawn Dsouza**

Computer Engineering Student | Aspiring Software & Game Developer

<p>
  <a href="https://github.com/soul2209">
    <img src="https://img.shields.io/badge/GitHub-soul2209-181717?style=for-the-badge&logo=github"/>
  </a>
  <a href="https://github.com/soul2209/packaged-food-analyser">
    <img src="https://img.shields.io/badge/Project-Repository-238636?style=for-the-badge&logo=github"/>
  </a>
</p>

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:14532D,100:7EE787&height=120&section=footer"/>
</p>

<p align="center">
  <strong>Read the label. Decode the ingredients. Make informed choices. 🥗</strong>
</p>
