# Sentiment Analysis System

## Introduction

This project is an AI-powered sentiment analysis and rumor monitoring system designed to process social media and news content related to stock markets.

The system collects and analyzes text data from multiple sources, extracts stock-related information, performs sentiment classification, summarizes discussions, detects trending topics, and generates insights for further analysis.

The project is built with Python and integrates NLP, machine learning, and database processing workflows.

---

# Features

* Sentiment analysis for social media and news content
* Stock symbol and keyword extraction
* Rumor detection and rumor analysis
* Text summarization and content rewriting
* Trending keyword analysis
* Training and evaluation pipelines for custom AI models
* PostgreSQL database integration
* Docker and Docker Compose support
* Batch processing and scheduler support
* Logging and statistics generation

---

# Project Structure

```bash
sentiment-analysis-main/
│
├── config/                 # Database configuration
├── models/                 # Database models and table creation
├── services/               # Core business logic and NLP services
├── training/               # Model training and evaluation scripts
├── rumor/                  # Rumor analysis modules
├── summary/                # Sentiment summary modules
├── trending_words/         # Trending keyword analysis
├── calendar/               # Economic calendar processing
├── yt_advise/              # YouTube-related scheduler tools
├── trained_models/         # Saved AI models
├── logs/                   # Application logs
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── main.py
```

---

# Prerequisites

Before running the project, make sure the following tools are installed:

* Python 3.9+
* PostgreSQL
* pip
* Docker (optional)
* Docker Compose (optional)

---

# Installation

## 1. Clone the Repository

```bash
git clone <repository-url>
cd sentiment-analysis-main
```

## 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment:

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Configuration

Create a `.env` or `.env.docker` file and configure the database connection.

Example:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sentiment_db
DB_USER=postgres
DB_PASSWORD=password
```

---

# Getting Started

## Run the Application

```bash
python main.py
```

## Run with Docker

```bash
docker-compose up --build
```

---

# Training Models

The project includes scripts for training and evaluating custom NLP models.

## Train Sentiment Model

```bash
python training/train_sentiment_model.py
```

## Evaluate Model

```bash
python training/evaluate_model.py
```

---

# Technologies Used

* Python
* PyTorch
* Transformers (Hugging Face)
* PostgreSQL
* Pandas
* Scikit-learn
* NLTK
* Docker

---

# Notes

* Some modules require a properly configured PostgreSQL database.
* Pretrained or custom-trained models may need to be downloaded before execution.
* Docker deployment is recommended for production environments.

---

# License

This project is intended for educational and internal development purposes.

Developed as an AI-based sentiment analysis and market monitoring project.
