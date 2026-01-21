// JavaScript principal pour l'éditeur de templates

// Variables globales
let editor = null;
let currentFile = '';
let autoSaveTimer = null;
let isModified = false;

// Initialisation principale
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initialisation de l\'éditeur de templates');
    
    // Initialiser la recherche
    initializeSearch();
    
    // Initialiser le thème
    initializeTheme();
    
    // Initialiser les raccourcis clavier
    initializeKeyboardShortcuts();
    
    // Initialiser le gestionnaire de fichiers
    initializeFileManagement();
    
    // Initialiser les notifications
    initializeNotifications();
    
    console.log('✅ Éditeur initialisé avec succès');
});

// Fonction de recherche
function initializeSearch() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    let searchTimeout;
    searchInput.addEventListener('input', function(e) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            performSearch(e.target.value);
        }, 300);
    });
}

function performSearch(query) {
    const items = document.querySelectorAll('.template-item');
    const searchTerm = query.toLowerCase().trim();
    
    items.forEach(item => {
        const name = item.dataset.name || '';
        const path = item.dataset.path || '';
        
        if (searchTerm === '') {
            item.style.display = 'block';
            return;
        }
        
        const matches = name.includes(searchTerm) || 
                       path.toLowerCase().includes(searchTerm);
        
        item.style.display = matches ? 'block' : 'none';
    });
}

// Gestion du thème
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
}

function applyTheme(theme) {
    document.body.classList.toggle('dark-theme', theme === 'dark');
    
    // Mettre à jour l'icône du bouton thème
    const themeButton = document.querySelector('[onclick="toggleTheme()"] i');
    if (themeButton) {
        themeButton.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    }
}

// Raccourcis clavier
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+S ou Cmd+S : Sauvegarder
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveCurrentFile();
        }
        
        // Ctrl+F ou Cmd+F : Recherche
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            focusSearch();
        }
        
        // Ctrl+N ou Cmd+N : Nouveau fichier
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/create_new';
        }
        
        // Échap : Fermer l'éditeur
        if (e.key === 'Escape' && editor) {
            closeEditor();
        }
    });
}

function focusSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.focus();
        searchInput.select();
    }
}

// Gestion des fichiers
function initializeFileManagement() {
    // Initialiser les tooltips
    initializeTooltips();
    
    // Initialiser les confirmations
    initializeConfirmations();
}

function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function initializeConfirmations() {
    // Ajouter des confirmations pour les actions destructrices
    document.querySelectorAll('[data-confirm]').forEach(element => {
        element.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
}

// Édition de templates
function editTemplate(filename) {
    currentFile = filename;
    
    // Charger le contenu du fichier
    fetch(`/get_content/${encodeURIComponent(filename)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showEditor(filename, data.content);
            } else {
                showNotification('Erreur: ' + data.error, 'danger');
            }
        })
        .catch(error => {
            showNotification('Erreur réseau: ' + error, 'danger');
        });
}

function showEditor(filename, content) {
    // Masquer le panneau de bienvenue
    const welcomePanel = document.getElementById('welcomePanel');
    if (welcomePanel) {
        welcomePanel.style.display = 'none';
    }
    
    // Afficher le panneau d'édition
    const editorPanel = document.getElementById('editorPanel');
    if (editorPanel) {
        editorPanel.style.display = 'block';
        editorPanel.classList.add('fade-in');
    }
    
    // Mettre à jour le titre et le chemin
    const editorTitle = document.getElementById('editorTitle');
    const editorPath = document.getElementById('editorPath');
    if (editorTitle) {
        editorTitle.innerHTML = `<i class="bi bi-pencil-square"></i> Édition : ${filename}`;
    }
    if (editorPath) {
        editorPath.textContent = filename;
    }
    
    // Initialiser CodeMirror
    initializeCodeMirror(content);
    
    // Démarrer la surveillance des modifications
    startModificationTracking();
}

function initializeCodeMirror(content) {
    // Détruire l'instance précédente si elle existe
    if (editor) {
        editor.toTextArea();
    }
    
    const textarea = document.getElementById('codeEditor');
    if (!textarea) return;
    
    editor = CodeMirror.fromTextArea(textarea, {
        mode: 'stex',
        theme: 'monokai',
        lineNumbers: true,
        lineWrapping: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        extraKeys: {
            "Ctrl-S": function() { saveCurrentFile(); },
            "Cmd-S": function() { saveCurrentFile(); },
            "Ctrl-Z": editor.undo,
            "Cmd-Z": editor.undo,
            "Ctrl-Y": editor.redo,
            "Cmd-Y": editor.redo,
            "Ctrl-F": findText,
            "Cmd-F": findText,
            "F11": toggleFullscreen
        }
    });
    
    // Définir le contenu
    if (content) {
        editor.setValue(content);
    }
    
    // Écouter les changements
    editor.on('change', onEditorChange);
    editor.on('cursorActivity', onCursorActivity);
    
    // Focus sur l'éditeur
    setTimeout(() => editor.focus(), 100);
}

function onEditorChange() {
    isModified = true;
    markAsModified();
    scheduleAutoSave();
}

function onCursorActivity() {
    updateCursorPosition();
}

function markAsModified() {
    const title = document.getElementById('editorTitle');
    if (title && !title.innerHTML.includes('•')) {
        title.innerHTML += ' <span class="text-warning">•</span>';
    }
}

function markAsSaved() {
    const title = document.getElementById('editorTitle');
    if (title) {
        title.innerHTML = title.innerHTML.replace(' <span class="text-warning">•</span>', '');
    }
    isModified = false;
}

function updateCursorPosition() {
    if (!editor) return;
    
    const cursor = editor.getCursor();
    const position = `Ligne ${cursor.line + 1}, Colonne ${cursor.ch + 1}`;
    
    // Mettre à jour un élément de statut s'il existe
    const statusElement = document.getElementById('cursorPosition');
    if (statusElement) {
        statusElement.textContent = position;
    }
}

// Sauvegarde
function saveCurrentFile() {
    if (!editor || !currentFile) return;
    
    const content = editor.getValue();
    
    // Afficher l'indicateur de sauvegarde
    showSaveIndicator();
    
    fetch('/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            filename: currentFile,
            content: content
        })
    })
    .then(response => response.json())
    .then(data => {
        hideSaveIndicator();
        
        if (data.success) {
            markAsSaved();
            showNotification('Fichier sauvegardé avec succès', 'success');
            cancelAutoSave();
        } else {
            showNotification('Erreur: ' + data.error, 'danger');
        }
    })
    .catch(error => {
        hideSaveIndicator();
        showNotification('Erreur réseau: ' + error, 'danger');
    });
}

function showSaveIndicator() {
    const panel = document.getElementById('editorPanel');
    if (panel) {
        panel.classList.add('saving');
    }
}

function hideSaveIndicator() {
    const panel = document.getElementById('editorPanel');
    if (panel) {
        panel.classList.remove('saving');
    }
}

function scheduleAutoSave() {
    cancelAutoSave();
    autoSaveTimer = setTimeout(() => {
        if (isModified) {
            saveCurrentFile();
        }
    }, 30000); // 30 secondes
}

function cancelAutoSave() {
    if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = null;
    }
}

// Fonctions de l'éditeur
function findText() {
    if (!editor) return;
    editor.execCommand('findPersistent');
}

function toggleFullscreen() {
    if (!editor) return;
    editor.setOption('fullScreen', !editor.getOption('fullScreen'));
}

function insertAtCursor(before, after = '') {
    if (!editor) return;
    
    const cursor = editor.getCursor();
    editor.replaceRange(before + after, cursor);
    
    if (after) {
        const newCursor = {line: cursor.line, ch: cursor.ch + before.length};
        editor.setCursor(newCursor);
        editor.setSelection(newCursor, {line: newCursor.line, ch: newCursor.ch + after.length});
    }
    
    editor.focus();
}

function insertSnippet() {
    if (!editor) return;
    
    const snippets = {
        'tcolorbox': '\\begin{tcolorbox}[title={Titre}]\nContenu de la boîte\n\\end{tcolorbox}',
        'itemize': '\\begin{itemize}\n\\item Premier élément\n\\item Deuxième élément\n\\end{itemize}',
        'enumerate': '\\begin{enumerate}\n\\item Premier point\n\\item Deuxième point\n\\end{enumerate}',
        'table': '\\begin{table}[h]\n\\centering\n\\begin{tabular}{|c|c|}\n\\hline\nCol1 & Col2 \\\\\n\\hline\nDonnée1 & Donnée2 \\\\\n\\hline\n\\end{tabular}\n\\caption{Légende}\n\\end{table}',
        'figure': '\\begin{figure}[h]\n\\centering\n\\includegraphics[width=0.8\\textwidth]{image.png}\n\\caption{Légende}\n\\end{figure}',
        'verbatim': '\\begin{verbatim}\nCode ici\n\\end{verbatim}',
        'equation': '\\begin{equation}\nE = mc^2\n\\end{equation}',
        'jinja2-if': '{% if condition %}\n\n{% endif %}',
        'jinja2-for': '{% for item in items %}\n\n{% endfor %}'
    };
    
    // Créer un sélecteur de snippets
    const snippetList = Object.entries(snippets).map(([key, value]) => 
        `<option value="${key}">${key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>`
    ).join('');
    
    const modal = `
        <div class="modal fade" id="snippetModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Insérer un snippet</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <select class="form-select" id="snippetSelect">
                            <option value="">Choisir un snippet...</option>
                            ${snippetList}
                        </select>
                        <textarea class="form-control mt-3" id="snippetPreview" rows="8" readonly></textarea>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                        <button type="button" class="btn btn-primary" onclick="insertSelectedSnippet()">Insérer</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Ajouter au DOM et afficher
    document.body.insertAdjacentHTML('beforeend', modal);
    
    const snippetModal = new bootstrap.Modal(document.getElementById('snippetModal'));
    snippetModal.show();
    
    // Aperçu dynamique
    const select = document.getElementById('snippetSelect');
    const preview = document.getElementById('snippetPreview');
    
    select.addEventListener('change', function() {
        preview.value = snippets[this.value] || '';
    });
    
    // Nettoyer à la fermeture
    document.getElementById('snippetModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

function insertSelectedSnippet() {
    const selected = document.getElementById('snippetSelect').value;
    const snippets = {
        'tcolorbox': '\\begin{tcolorbox}[title={Titre}]\nContenu de la boîte\n\\end{tcolorbox}',
        'itemize': '\\begin{itemize}\n\\item Premier élément\n\\item Deuxième élément\n\\end{itemize}',
        'enumerate': '\\begin{enumerate}\n\\item Premier point\n\\item Deuxième point\n\\end{enumerate}',
        'table': '\\begin{table}[h]\n\\centering\n\\begin{tabular}{|c|c|}\n\\hline\nCol1 & Col2 \\\\\n\\hline\nDonnée1 & Donnée2 \\\\\n\\hline\n\\end{tabular}\n\\caption{Légende}\n\\end{table}',
        'figure': '\\begin{figure}[h]\n\\centering\n\\includegraphics[width=0.8\\textwidth]{image.png}\n\\caption{Légende}\n\\end{figure}',
        'verbatim': '\\begin{verbatim}\nCode ici\n\\end{verbatim}',
        'equation': '\\begin{equation}\nE = mc^2\n\\end{equation}',
        'jinja2-if': '{% if condition %}\n\n{% endif %}',
        'jinja2-for': '{% for item in items %}\n\n{% endfor %}'
    };
    
    if (selected && snippets[selected]) {
        editor.replaceSelection(snippets[selected]);
    }
    
    // Fermer le modal
    bootstrap.Modal.getInstance(document.getElementById('snippetModal')).hide();
}

function closeEditor() {
    if (!editor) return;
    
    // Vérifier s'il y a des modifications non sauvegardées
    if (isModified) {
        if (!confirm('Des modifications n\'ont pas été sauvegardées. Voulez-vous vraiment fermer ?')) {
            return;
        }
    }
    
    // Nettoyer
    cancelAutoSave();
    editor.toTextArea();
    editor = null;
    currentFile = '';
    isModified = false;
    
    // Masquer le panneau d'édition
    const editorPanel = document.getElementById('editorPanel');
    const welcomePanel = document.getElementById('welcomePanel');
    
    if (editorPanel) {
        editorPanel.style.display = 'none';
    }
    if (welcomePanel) {
        welcomePanel.style.display = 'block';
    }
}

// Gestion des fichiers
function downloadTemplate(filename) {
    window.open(`/download/${encodeURIComponent(filename)}`);
}

function previewTemplate(filename) {
    fetch(`/get_content/${encodeURIComponent(filename)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showPreviewModal(data.content, filename);
            } else {
                showNotification('Erreur: ' + data.error, 'danger');
            }
        })
        .catch(error => {
            showNotification('Erreur réseau: ' + error, 'danger');
        });
}

function showPreviewModal(content, filename) {
    const modal = document.getElementById('previewModal');
    const contentElement = document.getElementById('previewContent');
    
    if (contentElement) {
        contentElement.textContent = content;
    }
    
    // Mettre à jour le titre
    const title = modal.querySelector('.modal-title');
    if (title) {
        title.textContent = `Aperçu : ${filename}`;
    }
    
    const previewModal = new bootstrap.Modal(modal);
    previewModal.show();
}

function formatLaTeX() {
    if (!editor) return;
    
    let content = editor.getValue();
    
    // Formatter le code LaTeX
    content = content
        // Ajouter des sauts de ligne après les environnements
        .replace(/\\(begin|end)\{([^}]+)\}/g, '\n\\$1{$2}\n')
        // Formatter les sections
        .replace(/\\(sub)*section\{([^}]+)\}/g, '\n\\$1section{$2}\n')
        // Nettoyer les lignes vides multiples
        .replace(/\n\s*\n\s*\n/g, '\n\n')
        .trim();
    
    editor.setValue(content);
    showNotification('Code formaté', 'info');
}

// Surveillance des modifications avant de quitter
function startModificationTracking() {
    window.addEventListener('beforeunload', function(e) {
        if (isModified) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}

// Notifications
function initializeNotifications() {
    // Créer le conteneur de notifications s'il n'existe pas
    if (!document.getElementById('notificationContainer')) {
        const container = document.createElement('div');
        container.id = 'notificationContainer';
        container.className = 'position-fixed';
        container.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        document.body.appendChild(container);
    }
}

function showNotification(message, type = 'info', duration = 3000) {
    const container = document.getElementById('notificationContainer');
    if (!container) return;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.style.cssText = 'margin-bottom: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    container.appendChild(alert);
    
    // Auto-suppression
    setTimeout(() => {
        if (alert.parentNode) {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }
    }, duration);
}

// Utilitaires
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Export pour utilisation externe
window.TemplateEditor = {
    editTemplate,
    downloadTemplate,
    previewTemplate,
    saveCurrentFile,
    closeEditor,
    showNotification,
    toggleTheme
};

console.log('📝 Éditeur de templates chargé');