(async function() {
            const params = new URLSearchParams(window.location.search);
            const file = params.get('file');
            const type = params.get('type') || 'tips';
            if (!file) {
                document.getElementById('article-content').innerHTML = '<div class="error-box">❌ 缺少 file 参数</div>';
                return;
            }
            try {
                const api = type === 'industry' ? '/api/industry/content' : '/api/tips/content';
                const res = await fetch(`${api}?file=${encodeURIComponent(file)}`);
                const data = await res.json();
                if (data.error) {
                    document.getElementById('article-content').innerHTML = `<div class="error-box">❌ ${data.error}</div>`;
                    return;
                }
                document.getElementById('page-title').textContent = data.title;
                // Convert markdown to HTML (simple conversion)
                const html = renderMarkdown(data.content);
                document.getElementById('article-content').innerHTML = `<div class="article">${html}</div>`;
            } catch(e) {
                document.getElementById('article-content').innerHTML = `<div class="error-box">❌ 加载失败: ${e.message}</div>`;
            }
        })();

        function renderMarkdown(text) {
            // Escape HTML
            let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            
            // Code blocks (``` ... ```)
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
            
            // Inline code
            html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
            
            // Horizontal rules
            html = html.replace(/^---+\s*$/gm, '<hr>');
            
            // Blockquote
            html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
            
            // Headers
            html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
            
            // Bold and italic
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
            
            // Tables
            html = html.replace(/^\|(.+)\|$/gm, function(m) {
                if (m.includes('---')) return m;
                const cells = m.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('');
                return `<tr>${cells}</tr>`;
            });
            html = html.replace(/<tr>.*?<\/tr>/g, function(m) {
                if (!html.includes('<table>')) {
                    html = html.replace(m, '<table>' + m);
                    return m + '</table>';
                }
                return m;
            });
            // Wrap consecutive tr in table
            html = html.replace(/((?:<tr>.*?<\/tr>\n?)+)/g, function(m) {
                if (!m.includes('<table>')) return '<table>' + m + '</table>';
                return m;
            });
            
            // Lists
            html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
            html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>');
            
            // Numbered lists
            html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
            
            // Double line breaks = paragraph break (but not inside tables/lists)
            html = html.replace(/\n\n+/g, '</p><p>');
            
            // Single line break = space (within paragraphs)
            html = html.replace(/\n/g, ' ');
            
            // Wrap in paragraph if not already
            if (!html.startsWith('<')) html = '<p>' + html + '</p>';
            
            // Clean up nested paragraphs from block elements
            html = html.replace(/<\/p><p>/g, '\n');
            html = html.replace(/<\/?p>/g, '\n');
            
            // Merge consecutive blockquotes
            html = html.replace(/<blockquote>/g, '\n<blockquote>');
            html = html.replace(/<\/blockquote>/g, '</blockquote>\n');
            
            // Clean empty paragraphs
            html = html.replace(/\n{3,}/g, '\n\n');
            
            return html.trim();
        }