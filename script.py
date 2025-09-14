import pandas as pd
import webbrowser
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime, timedelta
from pathlib import Path

URL = "https://flic.tap.pt/FLIC_UI/flic.aspx?id=CPOR-LISC1-12H_ARR"
OUT = "voos_lisbon_arrivals.html"
TID = "wt114_wtMainContent_wtTableRecords"
HIGHLIGHTS = {"EY", "JD", "JJ", "TS", "UA", "3P", "6O", "AA", "EK"}
VALID = HIGHLIGHTS | {"EC"}

def scrape(url: str) -> pd.DataFrame:
    opts = Options()
    opts.add_argument("--headless")
    with webdriver.Firefox(options=opts) as driver:
        driver.get(url)
        try:
            table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, TID)))
        except TimeoutException:
            print("⏰ Timeout: tabela não carregou.")
            return pd.DataFrame()
        headers = [th.text.strip() for th in table.find_elements(By.TAG_NAME, "th")]
        rows = [[td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")] for tr in table.find_elements(By.TAG_NAME, "tr")[1:]]
    df = pd.DataFrame([r for r in rows if r and any(c in r[0].upper() for c in VALID)], columns=headers)

    # Criar coluna STD priorizando STA, depois ETA, depois ATA
    if "STD" not in df.columns:
        if "STA" in df.columns:
            df["STD"] = df["STA"]
        elif "ETA" in df.columns:
            df["STD"] = df["ETA"]
        elif "ATA" in df.columns:
            df["STD"] = df["ATA"]
        else:
            df["STD"] = ""

    # Remove colunas vazias
    return df.loc[:, df.apply(lambda col: ~(col.str.strip() == "").all() if col.dtype == "object" else True)]

def filter_atd(df: pd.DataFrame, hrs: int = 2) -> pd.DataFrame:
    if "ATD" not in df and "ATA" not in df:
        return df
    now = datetime.now()
    def check(t):
        if not t or not isinstance(t, str):
            return True
        try:
            dt = datetime.combine(now.date(), datetime.strptime(t, "%H:%M").time())
            if dt > now:
                dt -= timedelta(days=1)
            return now - dt <= timedelta(hours=hrs)
        except:
            return True
    # Para chegadas, checa "ATA" (Actual Time of Arrival); para partidas, "ATD"
    col_to_check = "ATA" if "ATA" in df else "ATD"
    return df[df[col_to_check].apply(check)]

def generate_html(df: pd.DataFrame, out: str) -> None:
    if df.empty:
        print("⚠️ DataFrame vazio.")
        return
    table_html = df.to_html(index=False, classes="display", table_id="voosTable", border=0)
    hl = list(HIGHLIGHTS)
    html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8"><title>Voos Lisboa - Chegadas</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<style>
body{{font-family:Arial,sans-serif;margin:40px}}
h1{{margin-bottom:20px}}
table{{width:100%}}
#clock{{position:fixed;top:10px;right:20px;font-size:28px;font-family:monospace;background:#fdf6b2;padding:10px 16px;border-radius:8px;box-shadow:0 0 6px rgba(0,0,0,.3);z-index:1}}
</style>
</head><body>
<h1>Voos - Chegadas Lisboa</h1>
{table_html}
<div id="clock"></div>
<script>
$(function(){{
    const siglas={hl};
    const idx=$('#voosTable thead th').filter((_,th)=>$(th).text().toUpperCase()==='REMARKS').index();
    $('#voosTable').DataTable({{paging:false,searching:false,info:false,ordering:false}});
    $('#voosTable tbody tr').each(function(){{
        const c=$(this).find('td'), f=c.eq(0).text().toUpperCase();
        if(siglas.some(s=>f.includes(s))) $(this).css({{'background-color':'yellow','font-weight':'bold'}});
        if(idx!==-1 && c.eq(idx).text().toUpperCase()==='CANCELED') c.eq(idx).css({{'color':'red','font-weight':'bold'}});
    }});
    setInterval(() => {{
        const d=new Date(), h=String(d.getHours()).padStart(2,'0'), m=String(d.getMinutes()).padStart(2,'0'), s=String(d.getSeconds()).padStart(2,'0');
        $('#clock').text(`🕒 ${{h}}:${{m}}:${{s}}`);
    }}, 1000);
}});
</script>
</body></html>"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open(Path(out).resolve().as_uri())
    print(f"✅ HTML criado: {out}")

def main():
    df = scrape(URL)
    df_filtered = filter_atd(df)
    generate_html(df_filtered, OUT)

if __name__ == "__main__":
    main()
