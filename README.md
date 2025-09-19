````markdown
# 📱 Mobile Price Compare — SerpApi + Streamlit

A **mobile phone price comparison tool** powered by  
[SerpApi (Google Shopping API)](https://serpapi.com/) and [Streamlit](https://streamlit.io/).

Easily find the **lowest price** for a given mobile model across top online retailers in India (Amazon, Flipkart, Croma, Reliance Digital, etc.).

---

## ✨ Features
- 🔍 Search any mobile model (e.g., `iPhone 14 Pro`, `Samsung Galaxy S24 Ultra`).
- ⚡ Real-time results using **Google Shopping via SerpApi**.
- 🏆 Automatically highlights **best match & cheapest offer**.
- 📊 Cluster similar listings (using fuzzy matching).
- 💾 Built-in **SQLite cache** for faster repeated queries.
- 🎨 Modern, styled UI using **Streamlit**.

---

## 🛠️ Tech Stack
- **Python 3.8+**
- [Streamlit](https://streamlit.io/) (frontend UI)
- [SerpApi](https://serpapi.com/) (Google Shopping backend)
- [SQLite](https://www.sqlite.org/) (cache storage)
- [Pandas](https://pandas.pydata.org/) (data handling)
- [RapidFuzz](https://github.com/maxbachmann/RapidFuzz) (fuzzy text matching, optional)

---

## 📦 Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/Hiteshgottapu/mobile-price-compare.git
   cd mobile-price-compare
````

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   .venv\Scripts\activate      # Windows
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

---

## 🔑 Setup SerpApi API Key

1. Get your **SerpApi API key** from [SerpApi](https://serpapi.com/).
2. Add it to your environment:

   * **Windows PowerShell**

     ```powershell
     setx SERPAPI_KEY "your_api_key_here"
     ```

   * **macOS/Linux**

     ```bash
     export SERPAPI_KEY="your_api_key_here"
     ```

   Or create a `.env` file in the project root:

   ```
   SERPAPI_KEY=your_api_key_here
   ```

---

## ▶️ Usage

Run the app with:

```bash
streamlit run app.py
```

Then open the URL shown in your terminal (usually [http://localhost:8501](http://localhost:8501)).

---

## ⚙️ Project Structure

```
📂 mobile-price-compare/
 ├── app.py              # Streamlit app (main entry point)
 ├── aggregate.py        # Aggregates clustered results & finds cheapest price
 ├── product_cache.py    # SQLite-based caching for products
 ├── product_fetcher.py  # Fetches product data (using SerpApi client)
 ├── serpapi_client.py   # Handles communication with SerpApi
 ├── cache.sqlite        # Auto-created SQLite cache DB
 ├── requirements.txt    # Python dependencies
 ├── README.md           # Project documentation
 └── .env                # API key (not committed to Git)
```

---

## 🖼️ Example Workflow

1. Enter a query: **"Samsung Galaxy S24 Ultra"**
2. App fetches results from **Google Shopping (via SerpApi)**
3. Prices are clustered → **Best Deal highlighted**
4. Explore all offers (Amazon, Flipkart, Croma, etc.) with clickable links.

---

## ⚡ Roadmap

* [ ] Add **price tracking history** (trend charts).
* [ ] Multi-model comparison (compare iPhone vs Samsung).
* [ ] Email alerts when price drops.
* [ ] Extend support to global stores (US/UK markets).

---

## 📜 License

MIT License © 2025 [Hitesh](https://github.com/Hiteshgottapu)

---

```

---

👉 Do you also want me to **write the `requirements.txt`** for you based on this structure so it works out-of-the-box?
```

