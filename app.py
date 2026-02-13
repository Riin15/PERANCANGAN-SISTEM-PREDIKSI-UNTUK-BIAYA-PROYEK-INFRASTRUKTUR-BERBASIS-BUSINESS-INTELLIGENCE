from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import joblib
import secrets
import csv
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ==================== MODEL & ENCODER ========================
model = joblib.load('model_prediksi.model')
le_kota = joblib.load('le_Kota.joblib')
le_lokasi = joblib.load('le_Lokasi.joblib')
le_jenis_pembangunan = joblib.load('le_Jenis_Pembangunan.joblib')
le_jenis_pekerjaan = joblib.load('le_Jenis_Pekerjaan.joblib')
le_uraian_pekerjaan = joblib.load('le_Uraian_Pekerjaan.joblib')
le_satuan = joblib.load('le_Satuan.joblib')

# ================== SAFE TRANSFORM ===========================
def safe_transform(le, value):
    return le.transform([value])[0] if value in le.classes_ else -1

# =============== SIMPAN KE CSV (LOKAL) =======================
def simpan_ke_csv(data, filename='hasil_prediksi.csv'):
    file_exists = os.path.isfile(filename)
    with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# =============== SIMPAN KE GOOGLE SHEETS ======================
def simpan_ke_google_sheet(data):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open("hasil_prediksi").sheet1
    sheet.append_row([
        data['Kota'],
        data['Lokasi'],
        data['Jenis_Pembangunan'],
        data['Jenis_Pekerjaan'],
        data['Uraian_Pekerjaan'],
        data['Volume'],
        data['Satuan'],
        data['Harga_Satuan'],
        data['Prediction'],
        data['Kategori'],
        data['Tanggal']
    ])

# =============== BACA DARI GOOGLE SHEETS ======================
def baca_dari_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open("hasil_prediksi").sheet1
    records = sheet.get_all_records()
    return records

# ====================== FORM INFORMASI PROYEK =========================
@app.route('/save_project_info', methods=['POST'])
def save_project_info():
    session['project_info'] = {
        'Sub_Kegiatan': request.form['Sub_Kegiatan'],
        'Pekerjaan': request.form['Pekerjaan'],
        'Lokasi_Proyek': request.form['Lokasi_Proyek']
    }
    session.modified = True
    return redirect(url_for('home'))

# =========================== HALAMAN UTAMA ============================
@app.route('/', methods=['GET', 'POST'])
def home():
    error = None

    # Ambil dari Google Sheet jika session kosong
    if 'results' not in session or not session['results']:
        try:
            session['results'] = baca_dari_google_sheet()
        except Exception as e:
            error = f"Gagal memuat dari Google Sheets: {str(e)}"

    if request.method == 'POST':
        try:
            # Ambil data dari form
            kota = request.form['Kota'].strip().lower()
            lokasi = request.form['Lokasi'].strip().lower()
            jenis_pembangunan = request.form['Jenis_Pembangunan'].strip().lower()
            jenis_pekerjaan = request.form['Jenis_Pekerjaan'].strip().lower()
            uraian = request.form['Uraian_Pekerjaan'].strip().lower()
            volume = float(request.form['Volume'])
            satuan = request.form['Satuan'].strip().lower()
            harga_satuan = float(request.form['Harga_Satuan'])

            # Siapkan data untuk model
            input_df = pd.DataFrame([{
                'kota': safe_transform(le_kota, kota),
                'lokasi': safe_transform(le_lokasi, lokasi),
                'jenis_pembangunan': safe_transform(le_jenis_pembangunan, jenis_pembangunan),
                'jenis_pekerjaan': safe_transform(le_jenis_pekerjaan, jenis_pekerjaan),
                'uraian_pekerjaan': safe_transform(le_uraian_pekerjaan, uraian),
                'volume': volume,
                'satuan': safe_transform(le_satuan, satuan),
                'harga_satuan': harga_satuan
            }])

            # Prediksi dan pastikan tidak negatif
            prediction = model.predict(input_df)[0]

            manual_total = volume * harga_satuan
            prediction = max(0, prediction)

            # Ganti prediksi jika terlalu besar atau terlalu kecil dari nilai wajar
            if prediction > manual_total * 3 or prediction > 100_000_000 or prediction < manual_total * 0.3:
                prediction = manual_total

            # Simpan hasil
            result = {
                'Kota': kota,
                'Lokasi': lokasi,
                'Jenis_Pembangunan': jenis_pembangunan,
                'Jenis_Pekerjaan': jenis_pekerjaan,
                'Uraian_Pekerjaan': uraian,
                'Volume': volume,
                'Satuan': satuan,
                'Harga_Satuan': harga_satuan,
                'Prediction': prediction,  
                'Kategori': jenis_pekerjaan,
                'Tanggal': datetime.today().strftime('%Y-%m-%d')
            }

            # Simpan ke session dan penyimpanan
            session['results'].append(result)
            session.modified = True
            simpan_ke_csv(result)
            simpan_ke_google_sheet(result)

            return redirect(url_for('home'))

        except Exception as e:
            error = str(e)

    return render_template(
        'index.html',
        results=session.get('results', []),
        project_info=session.get('project_info'),
        error=error
    )

# ======================= HAPUS SATU HASIL ============================
@app.route('/delete/<int:index>')
def delete(index):
    if 'results' in session and 0 <= index < len(session['results']):
        session['results'].pop(index)
        session.modified = True
    return redirect(url_for('home'))

# ===================== HAPUS SEMUA HASIL =============================
@app.route('/clear', methods=['POST'])
def clear_all():
    # Hapus dari session
    session.pop('results', None)

    # Hapus dari Google Sheets
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)

        sheet = client.open("hasil_prediksi").sheet1
        total_rows = len(sheet.get_all_values())

        if total_rows > 1:
            sheet.delete_rows(2, total_rows)  # Hapus semua data kecuali header
    except Exception as e:
        print("Gagal hapus Google Sheet:", str(e))

    # Hapus isi file CSV lokal juga
    try:
        with open('hasil_prediksi.csv', 'w', encoding='utf-8') as f:
            f.truncate()  # kosongkan file
    except Exception as e:
        print("Gagal hapus CSV lokal:", str(e))

    return redirect(url_for('home'))

# ========================= RUN APP ===============================
if __name__ == '__main__':
    app.run(debug=True)
