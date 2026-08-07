import os
import sys
import socket
import math
import re
import webbrowser
import logging
import urllib.parse
from threading import Timer
from flask import Flask, request, Response, send_file, render_template_string, jsonify
import qrcode

# Konfigurasi Flask Logger agar tidak terlalu banyak mencetak log request stream
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

app = Flask(__name__)

# Format ekstensi video yang didukung
SUPPORTED_EXTENSIONS = ('.mp4', '.mkv', '.webm', '.avi')

def get_local_ip():
    """Mendapatkan alamat IP lokal komputer di jaringan Wi-Fi/LAN."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Menghubungkan ke IP publik (tidak benar-benar mengirim paket)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_watch_dir():
    """Mendapatkan direktori kerja video (berdasarkan lokasi EXE atau skrip)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def format_size(size_bytes):
    """Mengubah ukuran bytes menjadi unit yang mudah dibaca (KB, MB, GB)."""
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def get_mime_type(filepath):
    """Mendapatkan tipe MIME berdasarkan ekstensi file."""
    ext = os.path.splitext(filepath)[1].lower()
    mapping = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo'
    }
    return mapping.get(ext, 'application/octet-stream')

def find_thumbnail(watch_dir, rel_path):
    """Mencari file gambar (thumbnail) lokal dengan nama yang sama dengan video."""
    base, _ = os.path.splitext(rel_path)
    # Cari dengan berbagai ekstensi gambar umum
    for ext in ('.jpg', '.png', '.jpeg', '.webp', '.JPG', '.PNG', '.JPEG', '.WEBP'):
        thumb_path = os.path.join(watch_dir, base + ext)
        if os.path.exists(thumb_path):
            return (base + ext).replace(os.sep, '/')
    return None

def scan_videos():
    """Melakukan pemindaian file video di direktori watch secara rekursif."""
    watch_dir = get_watch_dir()
    video_files = []
    
    for root, dirs, files in os.walk(watch_dir):
        # Abaikan folder tersembunyi
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.lower().endswith(SUPPORTED_EXTENSIONS):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, watch_dir)
                size_bytes = os.path.getsize(full_path)
                
                # Cari thumbnail lokal
                thumb_rel = find_thumbnail(watch_dir, rel_path)
                
                video_files.append({
                    'name': file,
                    'rel_path': rel_path.replace(os.sep, '/'),  # Pakai slash agar seragam di URL
                    'size': format_size(size_bytes),
                    'size_bytes': size_bytes,
                    'thumbnail': thumb_rel
                })
    
    # Urutkan berdasarkan nama file secara alfabetis
    video_files.sort(key=lambda x: x['name'].lower())
    return video_files

# --- HTML TEMPLATE (Sleek Dark Dashboard) ---
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NontonFilm Lokal - Server</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Outfit', sans-serif;
            background-color: #0b111e;
        }
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #0b111e;
        }
        ::-webkit-scrollbar-thumb {
            background: #1e293b;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #3b82f6;
        }
    </style>
</head>
<body class="text-slate-100 min-h-screen flex flex-col">
    <!-- Navbar / Header -->
    <header class="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40 transition-colors duration-300">
        <div class="max-w-6xl mx-auto px-4 py-4 flex flex-col sm:flex-row justify-between items-center gap-4">
            <div class="flex items-center gap-3">
                <div class="p-2 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl shadow-lg shadow-indigo-500/20">
                    <!-- Play Icon -->
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <div>
                    <h1 class="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">NontonFilm Lokal</h1>
                    <p class="text-xs text-slate-400">Portable Local Media Server</p>
                </div>
            </div>
            
            <div class="flex flex-wrap items-center gap-3">
                <!-- IP Badge -->
                <div class="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-full text-emerald-400 text-sm font-medium">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
                    <span>Server: {{ ip }}:5000</span>
                </div>
                
                <!-- Refresh Button -->
                <button onclick="refreshMovies()" id="refreshBtn" class="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 active:scale-95 transition px-4 py-1.5 rounded-lg text-sm font-medium border border-slate-700">
                    <svg id="refreshIcon" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8H18.2" />
                    </svg>
                    Refresh
                </button>
            </div>
        </div>
    </header>

    <main class="flex-grow max-w-6xl w-full mx-auto px-4 py-8">
        <!-- Dashboard Greeting / Info -->
        <div class="bg-gradient-to-r from-slate-900 via-slate-900/90 to-indigo-950/20 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-8 relative overflow-hidden">
            <div class="absolute right-0 top-0 w-64 h-64 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none"></div>
            <div class="relative z-10">
                <h2 class="text-2xl sm:text-3xl font-bold mb-2">Selamat Datang di Bioskop Pribadimu! 🍿</h2>
                <p class="text-slate-400 max-w-2xl text-sm sm:text-base mb-6">
                    Aplikasi ini mendeteksi film di folder komputer Anda secara otomatis dan membagikannya ke perangkat lain di jaringan Wi-Fi/LAN yang sama.
                </p>
                <div class="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
                    <div class="bg-slate-950/60 backdrop-blur px-4 py-3 rounded-xl border border-slate-800/80">
                        <span class="block text-xs text-slate-500 uppercase tracking-wider font-semibold">Tonton di HP/Tablet</span>
                        <span class="text-sm font-mono text-blue-400">Hubungkan perangkat Anda ke Wi-Fi yang sama, lalu scan QR Code atau buka browser ke <strong class="underline select-all">http://{{ ip }}:5000</strong></span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Search Bar -->
        <div class="mb-8 max-w-md">
            <div class="relative">
                <span class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-slate-400">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </span>
                <input type="text" id="searchInput" oninput="filterMovies()" placeholder="Cari judul film..." 
                       class="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-xl py-3 pl-10 pr-4 outline-none transition text-slate-100 placeholder-slate-500">
            </div>
        </div>

        <!-- Movies Section -->
        <div>
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-lg font-semibold flex items-center gap-2">
                    Daftar Film Terdeteksi
                    <span id="movieCount" class="bg-slate-800 text-slate-400 text-xs px-2.5 py-1 rounded-full border border-slate-700">0</span>
                </h3>
            </div>

            <!-- Loading Spinner -->
            <div id="loading" class="flex flex-col items-center justify-center py-20">
                <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mb-4"></div>
                <p class="text-slate-500 text-sm">Memindai file video...</p>
            </div>

            <!-- Empty State -->
            <div id="emptyState" class="hidden border border-dashed border-slate-800 rounded-2xl py-16 px-4 text-center">
                <div class="inline-flex p-4 bg-slate-900 rounded-full text-slate-600 mb-4">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                    </svg>
                </div>
                <h4 class="text-lg font-medium text-slate-300 mb-1">Tidak Ada File Film Ditemukan</h4>
                <p class="text-slate-500 max-w-sm mx-auto text-sm mb-6">
                    Pindahkan file video dengan format <b>.mp4</b>, <b>.mkv</b>, <b>.webm</b>, atau <b>.avi</b> ke folder tempat aplikasi ini dijalankan.
                </p>
                <button onclick="refreshMovies()" class="bg-indigo-600 hover:bg-indigo-700 active:scale-95 transition text-white px-5 py-2.5 rounded-xl font-medium shadow-lg shadow-indigo-500/20 text-sm">
                    Scan Ulang Sekarang
                </button>
            </div>

            <!-- Movies Grid -->
            <div id="moviesGrid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 hidden">
                <!-- Movie cards injected by JavaScript -->
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-900 bg-slate-950/40 py-6 mt-12">
        <div class="max-w-6xl mx-auto px-4 text-center text-xs text-slate-500 flex flex-col gap-1">
            <p>NontonFilm Lokal &bull; Portable Server berbasis Python & Flask</p>
            <p>Created by <a href="https://www.instagram.com/riki.setiawan92/" target="_blank" rel="noopener noreferrer" class="text-indigo-400 hover:text-indigo-300 hover:underline">Riki Setiawan</a></p>
        </div>
    </footer>

    <!-- Video Player Modal Overlay -->
    <div id="playerModal" class="fixed inset-0 bg-slate-950/95 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden w-full max-w-4xl shadow-2xl relative flex flex-col max-h-[90vh]">
            <!-- Modal Header -->
            <div class="px-6 py-4 border-b border-slate-800 flex justify-between items-center">
                <div class="truncate pr-4">
                    <h4 id="modalMovieTitle" class="font-bold text-slate-100 truncate">Judul Film</h4>
                    <p id="modalMovieFolder" class="text-xs text-slate-400 truncate mt-0.5">Folder</p>
                </div>
                <button onclick="closePlayer()" class="bg-slate-800 hover:bg-slate-700 text-slate-300 p-2 rounded-full transition active:scale-95">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                </button>
            </div>
            
            <!-- Video Player Element container -->
            <div class="bg-black flex-grow flex items-center justify-center aspect-video relative">
                <video id="videoPlayer" class="w-full h-full" controls preload="auto" playsinline>
                    Browser Anda tidak mendukung pemutaran video secara langsung.
                </video>
            </div>
            
            <!-- Warning / Info banner in Modal for non-native files -->
            <div id="formatWarning" class="hidden px-6 py-3 bg-amber-500/10 border-t border-amber-500/20 text-amber-400 text-xs flex gap-2 items-start">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>
                    Format file ini (.mkv atau .avi) tidak didukung secara penuh oleh browser bawaan. Jika tidak ada suara atau layar hitam, disarankan untuk mengonversi file ke format <b>.mp4 (codec H.264/AAC)</b> atau membukanya di browser Google Chrome / Edge versi desktop.
                </span>
            </div>
        </div>
    </div>

    <!-- Script JavaScript -->
    <script>
        let allMovies = [];
        const thumbQueue = [];
        let thumbRunning = 0;
        const MAX_CONCURRENT_THUMBS = 2;

        window.onload = function() {
            fetchMovies();
        };

        function fetchMovies() {
            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('moviesGrid').classList.add('hidden');
            document.getElementById('emptyState').classList.add('hidden');

            fetch('/api/movies')
                .then(res => res.json())
                .then(data => {
                    allMovies = data;
                    renderMovies(allMovies);
                })
                .catch(err => {
                    console.error('Error fetching movies:', err);
                    document.getElementById('loading').classList.add('hidden');
                    document.getElementById('emptyState').classList.remove('hidden');
                });
        }

        function refreshMovies() {
            const btn = document.getElementById('refreshBtn');
            const icon = document.getElementById('refreshIcon');
            btn.disabled = true;
            icon.classList.add('animate-spin');

            fetch('/api/refresh')
                .then(res => res.json())
                .then(data => {
                    allMovies = data;
                    renderMovies(allMovies);
                    setTimeout(() => {
                        btn.disabled = false;
                        icon.classList.remove('animate-spin');
                    }, 500);
                })
                .catch(err => {
                    console.error('Error refreshing:', err);
                    btn.disabled = false;
                    icon.classList.remove('animate-spin');
                });
        }

        // Fungsi pembantu untuk membuat visual cover berbasis gradasi warna
        function getGradientStyle(name) {
            let hash = 0;
            for (let i = 0; i < name.length; i++) {
                hash = name.charCodeAt(i) + ((hash << 5) - hash);
            }
            const hue1 = Math.abs(hash % 360);
            const hue2 = (hue1 + 45) % 360;
            return `background: linear-gradient(135deg, hsl(${hue1}, 65%, 40%), hsl(${hue2}, 70%, 20%))`;
        }

        // Mendapatkan inisial film untuk ditampilkan di poster kosong
        function getInitials(name) {
            const base = name.substring(0, name.lastIndexOf('.')) || name;
            const words = base.replace(/[^a-zA-Z0-9\s]/g, ' ').trim().split(/\s+/);
            if (words.length >= 2) {
                return (words[0][0] + words[1][0]).toUpperCase();
            } else if (words.length === 1 && words[0].length > 0) {
                return words[0].substring(0, 2).toUpperCase();
            }
            return '🎬';
        }

        function renderMovies(movies) {
            document.getElementById('loading').classList.add('hidden');
            document.getElementById('movieCount').innerText = movies.length;

            const grid = document.getElementById('moviesGrid');
            grid.innerHTML = '';

            if (movies.length === 0) {
                document.getElementById('emptyState').classList.remove('hidden');
                grid.classList.add('hidden');
                return;
            }

            document.getElementById('emptyState').classList.add('hidden');
            grid.classList.remove('hidden');

            movies.forEach((movie, index) => {
                const ext = movie.name.split('.').pop().toLowerCase();
                let badgeColor = "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
                
                if (ext === 'mkv' || ext === 'avi') {
                    badgeColor = "bg-amber-500/10 text-amber-400 border-amber-500/20";
                } else if (ext === 'mp4' || ext === 'webm') {
                    badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
                }

                const parts = movie.rel_path.split('/');
                const subfolder = parts.length > 1 ? parts.slice(0, -1).join('/') + '/' : '';
                const gradientStyle = getGradientStyle(movie.name);
                const initials = getInitials(movie.name);

                // Buat struktur card seperti Netflix/YouTube (Vertical Card dengan Poster 16:9)
                const cardHtml = `
                    <div onclick="playMovie('${encodeURIComponent(movie.rel_path)}', '${movie.name.replace(/'/g, "\\'")}', '${subfolder.replace(/'/g, "\\'")}')" 
                         class="group bg-slate-900 border border-slate-800 hover:border-indigo-500/50 rounded-2xl cursor-pointer hover:shadow-xl hover:shadow-indigo-950/20 transition-all duration-300 transform hover:-translate-y-1 flex flex-col overflow-hidden h-72">
                        
                        <!-- Video Thumbnail Section (16:9 Aspect Ratio) -->
                        <div class="relative w-full aspect-video bg-slate-950 flex items-center justify-center overflow-hidden">
                            <!-- Image Element -->
                            <img id="img_${index}" class="w-full h-full object-cover hidden" alt="${movie.name}">
                            
                            <!-- Placeholder Cover Gradient -->
                            <div id="placeholder_${index}" style="${gradientStyle}" class="w-full h-full flex flex-col items-center justify-center p-4 text-center select-none relative transition-opacity duration-300">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-white/50 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                                </svg>
                                <span class="text-lg font-bold tracking-wider text-white">${initials}</span>
                            </div>
                            
                            <!-- Hover Play Overlay -->
                            <div class="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center">
                                <div class="bg-indigo-600 text-white p-2.5 rounded-full shadow-lg shadow-indigo-600/30 transform scale-90 group-hover:scale-100 transition-transform duration-300">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                    </svg>
                                </div>
                            </div>
                            
                            <!-- Format Extension Badge -->
                            <span class="absolute top-3 left-3 px-2 py-0.5 border text-[10px] font-semibold rounded-md ${badgeColor} uppercase tracking-wider">${ext}</span>
                            
                            <!-- Video Size Badge -->
                            <span class="absolute bottom-2 right-2 bg-slate-950/70 backdrop-blur text-[10px] px-2 py-0.5 rounded text-slate-300 font-medium">${movie.size}</span>
                        </div>

                        <!-- Card Info Section -->
                        <div class="p-4 flex-grow flex flex-col justify-between">
                            <h4 class="font-semibold text-slate-200 group-hover:text-indigo-400 text-sm transition-colors line-clamp-2" title="${movie.name}">
                                ${movie.name}
                            </h4>
                            <div class="flex items-center justify-between border-t border-slate-800/80 pt-3 mt-3">
                                <span class="text-[10px] text-slate-500 truncate max-w-[65%]" title="${subfolder || 'Direktori Utama'}">
                                    ${subfolder || 'Direktori Utama'}
                                </span>
                                <span class="flex items-center gap-1 text-xs text-indigo-400 font-semibold group-hover:translate-x-1 transition-transform">
                                    Putar
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                                        <path fill-rule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clip-rule="evenodd" />
                                    </svg>
                                </span>
                            </div>
                        </div>
                    </div>
                `;
                grid.innerHTML += cardHtml;

                // LOGIKA PENYAJIAN THUMBNAIL:
                const imgElementId = `img_${index}`;
                const placeholderId = `placeholder_${index}`;

                if (movie.thumbnail) {
                    // 1. Jika ada thumbnail lokal (.jpg/.png) yang dideteksi server
                    const img = document.getElementById(imgElementId);
                    const placeholder = document.getElementById(placeholderId);
                    img.src = `/stream/${encodeURIComponent(movie.thumbnail)}`;
                    img.classList.remove('hidden');
                    placeholder.classList.add('hidden');
                } else {
                    // 2. Cek apakah thumbnail hasil ekstraksi client-side sudah ada di cache localStorage
                    const cachedThumb = localStorage.getItem('thumb_' + movie.rel_path);
                    if (cachedThumb) {
                        const img = document.getElementById(imgElementId);
                        const placeholder = document.getElementById(placeholderId);
                        img.src = cachedThumb;
                        img.classList.remove('hidden');
                        placeholder.classList.add('hidden');
                    } else if (ext === 'mp4' || ext === 'webm') {
                        // 3. Jika file kompatibel dengan HTML5 video (MP4/WebM), masukkan ke antrean ekstraksi
                        queueThumbnailGeneration(movie.rel_path, `/stream/${encodeURIComponent(movie.rel_path)}`, imgElementId, placeholderId);
                    }
                }
            });
        }

        // --- Logika Ekstraksi Video Frame Client-Side ---
        function queueThumbnailGeneration(relPath, videoUrl, imgId, placeholderId) {
            thumbQueue.push({ relPath, videoUrl, imgId, placeholderId });
            processThumbQueue();
        }

        function processThumbQueue() {
            if (thumbRunning >= MAX_CONCURRENT_THUMBS || thumbQueue.length === 0) return;
            
            thumbRunning++;
            const item = thumbQueue.shift();
            
            generateClientThumbnail(item.videoUrl, (dataUrl) => {
                if (dataUrl) {
                    // Simpan ke cache localStorage agar pemuatan selanjutnya instan
                    try {
                        localStorage.setItem('thumb_' + item.relPath, dataUrl);
                    } catch (e) {
                        // Jika storage penuh, abaikan saja
                    }
                    
                    const img = document.getElementById(item.imgId);
                    const placeholder = document.getElementById(item.placeholderId);
                    if (img && placeholder) {
                        img.src = dataUrl;
                        img.classList.remove('hidden');
                        placeholder.classList.add('hidden');
                    }
                }
                thumbRunning--;
                processThumbQueue();
            });
        }

        function generateClientThumbnail(videoUrl, callback) {
            const video = document.createElement('video');
            video.src = videoUrl;
            video.preload = 'auto';
            video.muted = true;
            video.playsInline = true;
            
            // Cari frame pada detik ke-2 untuk menghindari gambar hitam di detik awal
            video.currentTime = 2;
            
            let isHandled = false;
            
            video.onseeked = function() {
                if (isHandled) return;
                isHandled = true;
                try {
                    const canvas = document.createElement('canvas');
                    canvas.width = 320;
                    canvas.height = 180;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    // Simpan sebagai jpeg dengan kompresi 0.7 agar hemat memory cache
                    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
                    callback(dataUrl);
                } catch (e) {
                    callback(null);
                }
                cleanup();
            };
            
            video.onerror = function() {
                if (isHandled) return;
                isHandled = true;
                callback(null);
                cleanup();
            };
            
            // Timeout jika file video gagal dimuat
            const timeout = setTimeout(() => {
                if (isHandled) return;
                isHandled = true;
                callback(null);
                cleanup();
            }, 5000);
            
            function cleanup() {
                clearTimeout(timeout);
                video.pause();
                video.src = "";
                video.load();
            }
        }

        function filterMovies() {
            const query = document.getElementById('searchInput').value.toLowerCase().trim();
            const filtered = allMovies.filter(movie => movie.name.toLowerCase().includes(query));
            renderMovies(filtered);
        }

        function playMovie(relPath, name, folder) {
            const player = document.getElementById('videoPlayer');
            const modal = document.getElementById('playerModal');
            const warning = document.getElementById('formatWarning');
            
            document.getElementById('modalMovieTitle').innerText = name;
            document.getElementById('modalMovieFolder').innerText = folder || 'Direktori Utama';

            // Cek ekstensi file
            const ext = name.split('.').pop().toLowerCase();
            if (ext === 'mkv' || ext === 'avi') {
                warning.classList.remove('hidden');
            } else {
                warning.classList.add('hidden');
            }

            // Set source video ke streaming endpoint
            player.src = `/stream/${relPath}`;
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden'; // Kunci scroll halaman belakang
            player.play().catch(e => console.log("Auto-play blocked or failed:", e));
        }

        function closePlayer() {
            const player = document.getElementById('videoPlayer');
            const modal = document.getElementById('playerModal');
            
            player.pause();
            player.src = ""; // Bersihkan source agar tidak memakan bandwidth
            modal.classList.add('hidden');
            document.body.style.overflow = ''; // Aktifkan kembali scroll
        }
    </script>
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, ip=get_local_ip())

@app.route('/api/movies')
def api_movies():
    return jsonify(scan_videos())

@app.route('/api/refresh')
def api_refresh():
    return jsonify(scan_videos())

@app.route('/stream/<path:filename>')
def stream_video(filename):
    # Dapatkan file path absolut
    watch_dir = get_watch_dir()
    # decode URL-encoded path
    decoded_filename = urllib.parse.unquote(filename)
    safe_path = os.path.abspath(os.path.join(watch_dir, decoded_filename))
    
    # Keamanan: Pastikan file berada di dalam folder watch_dir
    if not safe_path.startswith(os.path.abspath(watch_dir)):
        return "Akses Ditolak", 403
        
    if not os.path.exists(safe_path):
        return "File Tidak Ditemukan", 404
        
    mime = get_mime_type(safe_path)
    
    # send_file dengan conditional=True secara otomatis mendukung Range HTTP 206
    return send_file(safe_path, mimetype=mime, conditional=True)

# --- Server Start & Setup ---

if __name__ == '__main__':
    # Memastikan standard output menggunakan UTF-8 agar QR Code ASCII bisa tercetak dengan benar di Windows
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
        
    local_ip = get_local_ip()
    server_url = f"http://{local_ip}:5000"
    
    print("=" * 60)
    print("           NONTON FILM LOKAL - PORTABLE MEDIA SERVER")
    print("=" * 60)
    print(f"Direktori Film : {get_watch_dir()}")
    print(f"Status Server  : Aktif")
    print(f"Alamat Server  : {server_url}")
    print("-" * 60)
    print("Silakan pindahkan file video ke direktori film di atas.")
    print("Scan QR Code di bawah dengan HP Anda untuk menonton langsung:")
    print("-" * 60)
    
    # Generate QR Code dan tampilkan di konsol
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2
        )
        qr.add_data(server_url)
        qr.make(fit=True)
        # Menampilkan QR Code ASCII di konsol
        qr.print_ascii()
    except Exception as e:
        print(f"[Warning] Gagal mencetak QR Code: {e}")
        
    print("-" * 60)
    print("Tekan Ctrl+C di jendela konsol ini untuk menghentikan server.")
    print("=" * 60)
    
    # Buka browser default secara otomatis setelah 1.5 detik
    def open_browser():
        try:
            webbrowser.open(server_url)
        except Exception:
            pass
            
    Timer(1.5, open_browser).start()
    
    # Jalankan server Flask pada IP lokal dan port 5000
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
