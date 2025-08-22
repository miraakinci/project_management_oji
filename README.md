# OJI Project Management System

The project management system is a web-based application designed to streamline and enhance the process of managing complex projects. It provides a centralized platform for project managers and team members to track project progress, manage resources, and collaborate effectively. The system is built upon a robust and scalable architecture that integrates a traditional relational database with a modern vector database to offer both standard project management functionalities and advanced AI-powered features, such as semantic search. This hybrid approach allows the system to handle structured project data with the reliability of a relational database, while also leveraging the power of vector embeddings for intelligent data retrieval and analysis.

---

## Requirements
- **Python 3.10 or later** 

---

## User Guide

Follow these steps to set up and start the application:

### 1. Clone the Repository 
```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

#Ensure the version is 3.10 or higher.
python --version

### 2. Create and activate the Virtual Environment 
python -m venv venv

```MAC/Linux
source venv/bin/activate

```Windows 
venv\Scripts\Activate

### 3. Install Dependencies 
pip install -r requirements.txt

### 3. Get an OpenAI API Key

Sign in or create an account at https://platform.openai.com/account/api-keys

Click “Create new secret key” and copy it.

Create a .env file in the project root (pm_app) and add:

OPENAI_API_KEY="your-api-key-here"
USE_MOCK="FALSE"
EVAL_MODEL="gpt-4o"

### 4. Run the Application 
python manage.py runserver

### This will start a local development server, usually at: http://127.0.0.1:8000/. Copy and paste the link into your browser, and you are ready to start planning your projects!

---

## Developer Guide

### To run the LLM Benchmarking Test, run this command on your terminal 

python llm_benchmark.py

###This will create a benchmarks folder in the project directory

###To run evaluation functions in pm_eval file you should put you API key on top of file for scripts : data_integration_eval.py and scalability_test.py




