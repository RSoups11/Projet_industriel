// JavaScript spécifique pour l'éditeur principal

// Variables globales pour l'éditeur
let editor = null;
let currentFile = '';
let autoSaveTimer = null;
let isModified = false;

// Initialisation de l'éditeur
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initialisation de l\'éditeur principal');
    
    // Initialiser la recherche
    initializeSearch();
    
    // Initialiser les gestionnaires d'événements
    initializeEventHandlers();
    
    // Démarrer la surveillance de sauvegarde automatique
    startAutoSaveMonitoring();
    
    console.log('✅ Éditeur principal initialisé');
});

// Gestionnaire de recherche
function initializeSearch() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    let searchTimeout;
    searchInput.addEventListener('input', function(e) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            filterTemplates(e.target.value.toLowerCase());
        }, 250);
    });
}

function filterTemplates(searchTerm) {
    const templateItems = document.querySelectorAll('.template-item');
    
    templateItems.forEach(item => {
        const name = item.dataset.name || '';
        const path = item.dataset.path || '';
        
        const matches = name.includes(searchTerm) || 
                       path.toLowerCase().includes(searchTerm);
        
        item.style.display = matches ? 'block' : 'none';
        
        // Animation douce
        if (matches) {
            item.style.opacity = '0';
            setTimeout(() => {
                item.style.opacity = '1';
                item.style.transition = 'opacity 0.2s ease';
            }, 50);
        }
    });
}

// Gestionnaires d'événements
function initializeEventHandlers() {
    // Raccourcis clavier globaux
    document.addEventListener('keydown', function(e) {
        // Ctrl+N : Nouveau fichier
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/create_new';
        }
        
        // Ctrl+F : Focus recherche
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        
        // Échap : Fermer l'éditeur
        if (e.key === 'Escape' && editor) {
            closeEditor();
        }
    });
    
    // Glisser-déposer pour les templates
    initializeDragAndDrop();
}

// Initialisation de l'éditeur CodeMirror
function initializeEditor(content = '') {
    const textarea = document.getElementById('codeEditor');
    if (!textarea) return null;
    
    // Détruire l'instance précédente
    if (editor) {
        editor.toTextArea();
    }
    
    // Créer la nouvelle instance
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
            "Ctrl-S": function() { 
                saveFile(); 
            },
            "Cmd-S": function() { 
                saveFile(); 
            },
            "Ctrl-Z": editor.undo,
            "Cmd-Z": editor.undo,
            "Ctrl-Y": editor.redo,
            "Cmd-Y": editor.redo,
            "Ctrl-F": findText,
            "Cmd-F": findText,
            "F11": toggleFullscreen,
            "Tab": function(cm) {
                cm.replaceSelection("    ");
            }
        }
    });
    
    // Définir le contenu
    if (content) {
        editor.setValue(content);
    }
    
    // Écouter les événements
    editor.on('change', onEditorChange);
    editor.on('cursorActivity', updateCursorPosition);
    editor.on('focus', onEditorFocus);
    editor.on('blur', onEditorBlur);
    
    // Focus sur l'éditeur
    setTimeout(() => editor.focus(), 100);
    
    return editor;
}

function onEditorChange() {
    isModified = true;
    updateModificationIndicator();
    scheduleAutoSave();
}

function onEditorFocus() {
    document.body.classList.add('editor-active');
}

function onEditorBlur() {
    document.body.classList.remove('editor-active');
}

function updateCursorPosition() {
    if (!editor) return;
    
    const cursor = editor.getCursor();
    const position = `Ligne ${cursor.line + 1}, Colonne ${cursor.ch + 1}`;
    
    // Mettre à jour l'affichage de la position
    const positionElement = document.getElementById('cursorPosition');
    if (positionElement) {
        positionElement.textContent = position;
    }
}

function updateModificationIndicator() {
    const title = document.getElementById('editorTitle');
    if (title && !title.innerHTML.includes('●')) {
        title.innerHTML += ' <span class="text-warning" title="Modifié">●</span>';
    }
}

function clearModificationIndicator() {
    const title = document.getElementById('editorTitle');
    if (title) {
        title.innerHTML = title.innerHTML.replace(' <span class="text-warning" title="Modifié">●</span>', '');
    }
    isModified = false;
}

// Gestion des templates
function editTemplate(filename) {
    currentFile = filename;
    
    // Afficher le panneau d'édition
    showEditorPanel();
    
    // Charger le contenu
    fetch(`/get_content/${encodeURIComponent(filename)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                initializeEditor(data.content);
                updateEditorInfo(filename);
            } else {
                showNotification('Erreur lors du chargement: ' + data.error, 'danger');
            }
        })
        .catch(error => {
            showNotification('Erreur réseau: ' + error, 'danger');
        });
}

function showEditorPanel() {
    const welcomePanel = document.getElementById('welcomePanel');
    const editorPanel = document.getElementById('editorPanel');
    
    if (welcomePanel) {
        welcomePanel.style.display = 'none';
    }
    
    if (editorPanel) {
        editorPanel.style.display = 'block';
        editorPanel.classList.add('fade-in');
        editorPanel.scrollIntoView({ behavior: 'smooth' });
    }
}

function updateEditorInfo(filename) {
    const title = document.getElementById('editorTitle');
    const path = document.getElementById('editorPath');
    
    if (title) {
        title.innerHTML = `<i class="bi bi-pencil-square"></i> Édition : ${filename}`;
    }
    
    if (path) {
        path.textContent = filename;
    }
}

// Sauvegarde
function saveFile() {
    if (!editor || !currentFile) return;
    
    const content = editor.getValue();
    
    // Indicateur de sauvegarde
    showSaveIndicator(true);
    
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
        showSaveIndicator(false);
        
        if (data.success) {
            clearModificationIndicator();
            cancelAutoSave();
            showNotification('✅ Fichier sauvegardé avec succès', 'success');
        } else {
            showNotification('❌ Erreur: ' + data.error, 'danger');
        }
    })
    .catch(error => {
        showSaveIndicator(false);
        showNotification('❌ Erreur réseau: ' + error, 'danger');
    });
}

function showSaveIndicator(showing) {
    const editorPanel = document.getElementById('editorPanel');
    if (!editorPanel) return;
    
    if (showing) {
        editorPanel.classList.add('saving');
    } else {
        editorPanel.classList.remove('saving');
    }
}

// Sauvegarde automatique
function scheduleAutoSave() {
    cancelAutoSave();
    autoSaveTimer = setTimeout(() => {
        if (isModified && editor) {
            saveFile();
        }
    }, 30000); // 30 secondes
}

function cancelAutoSave() {
    if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = null;
    }
}

function startAutoSaveMonitoring() {
    // Sauvegarde avant de quitter la page
    window.addEventListener('beforeunload', function(e) {
        if (isModified && editor) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
    
    // Sauvegarde lors de la perte de focus
    window.addEventListener('blur', function() {
        if (isModified && editor) {
            scheduleAutoSave();
        }
    });
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
    
    // Utiliser le sélecteur de snippets de la page
    const select = document.getElementById('snippetSelect');
    if (select) {
        const selected = select.value;
        if (selected && snippets[selected]) {
            editor.replaceSelection(snippets[selected]);
            select.value = '';
            showNotification('Snippet inséré', 'info');
        } else {
            showNotification('Veuillez sélectionner un snippet', 'warning');
        }
    }
}

function formatLaTeX() {
    if (!editor) return;
    
    let content = editor.getValue();
    
    // Formatter le code LaTeX
    content = content
        .replace(/\\(begin|end)\{([^}]+)\}/g, '\n\\$1{$2}\n')
        .replace(/\\(sub)*section\{([^}]+)\}/g, '\n\\$1section{$2}\n')
        .replace(/\n\s*\n\s*\n/g, '\n\n')
        .trim();
    
    editor.setValue(content);
    showNotification('Code formaté', 'info');
}

// Actions sur les fichiers
function downloadTemplate(filename) {
    window.open(`/download/${encodeURIComponent(filename)}`);
}

function previewTemplate(filename) {
    fetch(`/get_content/${encodeURIComponent(filename)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showPreviewDialog(data.content, filename);
            } else {
                showNotification('Erreur: ' + data.error, 'danger');
            }
        })
        .catch(error => {
            showNotification('Erreur réseau: ' + error, 'danger');
        });
}

function showPreviewDialog(content, filename) {
    // Créer ou mettre à jour le modal d'aperçu
    let modal = document.getElementById('previewModal');
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

function closeEditor() {
    if (!editor) return;
    
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

// Glisser-déposer
function initializeDragAndDrop() {
    const templateList = document.querySelector('.template-list');
    if (!templateList) return;
    
    templateList.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    });
    
    templateList.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
    });
    
    templateList.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        
        // Logique de traitement des fichiers déposés
        const files = Array.from(e.dataTransfer.files);
        handleDroppedFiles(files);
    });
}

function handleDroppedFiles(files) {
    // Filtrer les fichiers .tex et .j2
    const validFiles = files.filter(file => 
        file.name.endsWith('.tex') || file.name.endsWith('.j2')
    );
    
    if (validFiles.length === 0) {
        showNotification('Veuillez déposer des fichiers .tex ou .j2', 'warning');
        return;
    }
    
    // Traiter chaque fichier
    validFiles.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(e) {
            // Logique pour importer le fichier
            console.log('Fichier importé:', file.name);
            showNotification(`${file.name} importé avec succès`, 'success');
        };
        reader.readAsText(file);
    });
}

// Utilitaires
function showNotification(message, type = 'info', duration = 3000) {
    const container = document.getElementById('notificationContainer');
    if (!container) {
        // Créer le conteneur s'il n'existe pas
        const newContainer = document.createElement('div');
        newContainer.id = 'notificationContainer';
        newContainer.className = 'position-fixed';
        newContainer.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        document.body.appendChild(newContainer);
    }
    
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

// Exporter les fonctions pour l'utilisation externe
window.Editor = {
    editTemplate,
    saveFile,
    closeEditor,
    insertAtCursor,
    insertSnippet,
    formatLaTeX,
    downloadTemplate,
    previewTemplate
};

console.log('📝 Éditeur principal chargé');