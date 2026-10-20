/*
 * Copyright (C) 2026 Paulo Felipe Jarschel
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 */

import { useState, useRef, useCallback, useEffect, lazy, Suspense } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { useTranslation } from '../i18n';

const MonacoEditor = lazy(() => import('@monaco-editor/react'));

const BACKEND_URL = 'http://localhost:8000';

const getLanguageDefaultCode = (type: string) => {
  switch (type) {
    case 'script/lua':
      return `-- @input name="value" type="number" default=1.0\n-- @output name="result" type="number"\n\nresult = value * 2\n`;
    case 'script/julia':
      return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult = value * 2\n`;
    case 'script/javascript':
      return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nresult = value * 2;\n`;
    case 'script/typescript':
      return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nconst val: number = value;\nresult = val * 2;\n`;
    case 'script/rust':
      return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nresult = value * 2.0;\n`;
    case 'script/r':
      return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult <- value * 2\n`;
    case 'script/octave':
      return `% @input name="value" type="number" default=1.0\n% @output name="result" type="number"\n\nresult = value * 2;\n`;
    case 'script/wolfram':
      return `(* @input name="value" type="number" default=1.0 *)\n(* @output name="result" type="number" *)\n\nresult = value * 2;\n`;
    case 'script/sage':
    case 'script/sagemath':
      return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult = value * 2\n`;
    case 'script/maxima':
      return `/* @input name="value" type="number" default=1.0 */\n/* @output name="result" type="number" */\n\nresult: value * 2;\n`;
    case 'script/powershell':
    case 'script/pwsh':
      return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\n$result = $value * 2\n`;
    case 'script/csharp':
    case 'script/cs':
    case 'script/dotnet':
      return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nresult = value * 2;\n`;
    case 'script/python':
    default:
      return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult = value * 2\n`;
  }
};

interface ScriptEditorPanelProps {
  isOpen: boolean;
  code: string;
  blockId: string;
  actionType: string;
  onSave: (code: string, inputs: any[], outputs: any[]) => void;
  onClose: () => void;
  onCodeChange?: (blockId: string, code: string) => void;
  hasActiveWorkspace: boolean;
  onPublishSuccess: () => void;
  registryLayout?: {
    name: string;
    category: string;
    icon: string;
    description: string;
    script_language?: string;
  };
  appTheme?: 'dark' | 'light';
}

const handleEditorMount = (editor: any, monaco: any, langKey: string): { updateDeclarations?: (text: string) => void } => {
  if (!window || !(window as any).monaco) {
    (window as any).monaco = monaco;
  }

  // Register matlab language if not present (since Monaco basic-languages does not ship with it by default)
  if (!monaco.languages.getLanguages().some((l: any) => l.id === 'matlab')) {
    monaco.languages.register({ id: 'matlab' });
    monaco.languages.setMonarchTokensProvider('matlab', {
      defaultToken: '',
      keywords: [
        'break', 'case', 'catch', 'classdef', 'continue', 'else', 'elseif', 'end',
        'for', 'function', 'global', 'if', 'methods', 'otherwise', 'parfor',
        'persistent', 'properties', 'return', 'spmd', 'switch', 'try', 'while'
      ],
      operators: [
        '+', '-', '*', '/', '\\', '^', '.*', './', '.\\', '.^',
        '==', '~=', '<', '<=', '>', '>=', '&', '|', '&&', '||', '~', '='
      ],
      tokenizer: {
        root: [
          [/(%.*)/, 'comment'],
          [/[a-zA-Z_][a-zA-Z0-9_]*/, {
            cases: {
              '@keywords': 'keyword',
              '@default': 'identifier'
            }
          }],
          [/[{}()\[\]]/, '@brackets'],
          [/[<>:=!~&|+\-*\/\^%]/, 'operator'],
          [/\d*\.\d+([eE][\-+]?\d+)?/, 'number.float'],
          [/\d+([eE][\-+]?\d+)?/, 'number'],
          [/'([^'\\]|\\.)*'/, 'string'],
          [/"([^"\\]|\\.)*"/, 'string']
        ]
      }
    });
    
    // Set configuration for comments support (ctrl+/ shortcut support)
    monaco.languages.setLanguageConfiguration('matlab', {
      comments: {
        lineComment: '%'
      }
    });
  }

  // Register wolfram language if not present
  if (!monaco.languages.getLanguages().some((l: any) => l.id === 'wolfram')) {
    monaco.languages.register({ id: 'wolfram' });
    monaco.languages.setMonarchTokensProvider('wolfram', {
      defaultToken: '',
      keywords: [
        'If', 'While', 'For', 'Do', 'Module', 'Block', 'With', 'Table', 'Plot',
        'Export', 'Import', 'Print', 'Return', 'True', 'False', 'Null', 'ClearAll',
        'Evaluate', 'ReplaceAll', 'Map', 'Apply', 'Function'
      ],
      tokenizer: {
        root: [
          [/[A-Z][a-zA-Z0-9_]*/, {
            cases: {
              '@keywords': 'keyword',
              '@default': 'type.identifier'
            }
          }],
          [/[a-z_][a-zA-Z0-9_]*/, 'identifier'],
          [/\(\*/, 'comment', '@comment'],
          [/"([^"\\]|\\.)*"/, 'string'],
          [/\d*\.\d+/, 'number.float'],
          [/\d+/, 'number'],
          [/[{}()\[\]]/, '@brackets'],
          [/[+\-*\/=<>!&|@^]/, 'operator']
        ],
        comment: [
          [/[^\(*]+/, 'comment'],
          [/\*\)/, 'comment', '@pop'],
          [/\(\*/, 'comment', '@push'],
          [/[\(*]/, 'comment']
        ]
      }
    });
    
    // Set configuration for comments support (ctrl+/ shortcut support)
    monaco.languages.setLanguageConfiguration('wolfram', {
      comments: {
        blockComment: ['(*', '*)']
      }
    });
  }

  // Register maxima language if not present
  if (!monaco.languages.getLanguages().some((l: any) => l.id === 'maxima')) {
    monaco.languages.register({ id: 'maxima' });
    monaco.languages.setMonarchTokensProvider('maxima', {
      defaultToken: '',
      keywords: [
        'if', 'then', 'else', 'elseif', 'for', 'from', 'step', 'next', 'thru',
        'while', 'unless', 'do', 'return', 'block', 'true', 'false', 'matrix',
        'sin', 'cos', 'tan', 'exp', 'log', 'diff', 'integrate', 'sum', 'product',
        'solve', 'float', 'bfloat', 'print', 'printf', 'openw', 'openr', 'close',
        'quit', 'errcatch', 'args', 'length', 'sconcat', 'ssubst', 'string',
        'integerp', 'floatnump', 'numberp', 'stringp', 'listp', 'matrixp'
      ],
      operators: [
        '+', '-', '*', '/', '^', '**', ':', ':=', '::=', '::', '!', '!!',
        '=', '#', '>', '<', '>=', '<=', 'and', 'or', 'not', '$', ';'
      ],
      tokenizer: {
        root: [
          [/[a-zA-Z_%][a-zA-Z0-9_%]*/, {
            cases: {
              '@keywords': 'keyword',
              '@default': 'identifier'
            }
          }],
          [/\/\*/, 'comment', '@comment'],
          [/"([^"\\]|\\.)*"/, 'string'],
          [/\d*\.\d+([eE][\-+]?\d+)?/, 'number.float'],
          [/\d+/, 'number'],
          [/[{}()\[\]]/, '@brackets'],
          [/[+\-*\/=<>!&|@^:$#;]+/, 'operator']
        ],
        comment: [
          [/[^\/*]+/, 'comment'],
          [/\*\//, 'comment', '@pop'],
          [/\/\*/, 'comment', '@push'],
          [/[\/*]/, 'comment']
        ]
      }
    });

    monaco.languages.setLanguageConfiguration('maxima', {
      comments: {
        blockComment: ['/*', '*/']
      }
    });
  }

  // Set configuration for powershell comments support (ctrl+/ shortcut support)
  monaco.languages.setLanguageConfiguration('powershell', {
    comments: {
      lineComment: '#',
      blockComment: ['<#', '#>']
    }
  });

  let tsUpdateFn: ((text: string) => void) | undefined;

  if (langKey === 'typescript') {
    monaco.languages.typescript.typescriptDefaults.setCompilerOptions({
      target: monaco.languages.typescript.ScriptTarget.ES2020,
      allowNonTsExtensions: true,
      checkJs: false
    });

    let extraLibDisposable: any = null;

    const updateDeclarations = (text: string) => {
      if (extraLibDisposable) {
        extraLibDisposable.dispose();
      }

      // Parse input/output pin decorators dynamically from the editor text
      const inputRegex = /@input\s+name=["'](\w+)["']/g;
      let match;
      const foundPins = new Set<string>();
      while ((match = inputRegex.exec(text)) !== null) {
        foundPins.add(match[1]);
      }
      const outputRegex = /@output\s+name=["'](\w+)["']/g;
      while ((match = outputRegex.exec(text)) !== null) {
        foundPins.add(match[1]);
      }

      let declarations = `
declare const context: any;
declare const workspace: string;
`;
      foundPins.forEach(pinName => {
        declarations += `\ndeclare var ${pinName}: any;`;
      });

      extraLibDisposable = monaco.languages.typescript.typescriptDefaults.addExtraLib(
        declarations,
        'ts-declarations.d.ts'
      );
    };

    tsUpdateFn = updateDeclarations;

    // Initialize declarations on mount
    updateDeclarations(editor.getValue());

    // Listen to changes to keep declarations in sync as user types
    const changeSubscription = editor.onDidChangeModelContent(() => {
      updateDeclarations(editor.getValue());
    });

    // Clean up listeners on editor dispose to avoid memory leaks
    editor.onDidDispose(() => {
      if (extraLibDisposable) {
        extraLibDisposable.dispose();
      }
      changeSubscription.dispose();
    });
  }
  
  const key = `comfylab_completions_${langKey}`;
  if ((window as any)[key]) return { updateDeclarations: tsUpdateFn };
  (window as any)[key] = true;

  monaco.languages.registerCompletionItemProvider(langKey, {
    provideCompletionItems: (model: any, position: any) => {
      const text = model.getValue();
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn
      };

      const suggestions: any[] = [
        {
          label: 'context',
          kind: monaco.languages.CompletionItemKind.Variable,
          insertText: 'context',
          detail: 'ComfyLAB context',
          documentation: 'Dynamic execution context to pull/push variables.',
          range
        },
        {
          label: 'workspace',
          kind: monaco.languages.CompletionItemKind.Variable,
          insertText: 'workspace',
          detail: 'Workspace Path',
          documentation: 'String path to current workspace root directory.',
          range
        }
      ];

      if (langKey === 'python') {
        suggestions.push(
          {
            label: 'np',
            kind: monaco.languages.CompletionItemKind.Module,
            insertText: 'np',
            detail: 'NumPy module',
            documentation: 'Pre-imported Numerical Python.',
            range
          },
          {
            label: 'math',
            kind: monaco.languages.CompletionItemKind.Module,
            insertText: 'math',
            detail: 'Standard math module',
            documentation: 'Python math package.',
            range
          }
        );
      }

      // Parse input/output pin decorators dynamically from the editor text
      const inputRegex = /@input\s+name=["'](\w+)["']/g;
      let match;
      const foundPins = new Set<string>();
      while ((match = inputRegex.exec(text)) !== null) {
        foundPins.add(match[1]);
      }
      const outputRegex = /@output\s+name=["'](\w+)["']/g;
      while ((match = outputRegex.exec(text)) !== null) {
        foundPins.add(match[1]);
      }

      foundPins.forEach(pinName => {
        suggestions.push({
          label: pinName,
          kind: monaco.languages.CompletionItemKind.Field,
          insertText: pinName,
          detail: 'Script Pin Variable',
          documentation: 'Variable mapped dynamically from ComfyLAB pin comments.',
          range
        });
      });

      return { suggestions };
    }
  });

  return { updateDeclarations: tsUpdateFn };
};

export const ScriptEditorPanel = ({ 
  isOpen, 
  code, 
  blockId, 
  actionType, 
  onSave, 
  onClose,
  onCodeChange,
  hasActiveWorkspace, 
  onPublishSuccess,
  registryLayout,
  appTheme = 'dark'
}: ScriptEditorPanelProps) => {
  const { t } = useTranslation();
  const getLanguageDetails = () => {
    // Check registryLayout.script_language for published blocks
    const lang = registryLayout?.script_language || actionType;
    switch (lang) {
      case 'script/lua': case 'lua':
        return { name: 'Lua', langKey: 'lua', icon: '🌙', commentChar: '--', hint: 'scope: context, workspace' };
      case 'script/julia': case 'julia':
        return { name: 'Julia', langKey: 'julia', icon: '👩‍🏫', commentChar: '#', hint: 'scope: context, workspace' };
      case 'script/javascript': case 'javascript':
        return { name: 'JavaScript', langKey: 'javascript', icon: '☕', commentChar: '//', hint: 'scope: context, workspace' };
      case 'script/typescript': case 'typescript':
        return { name: 'TypeScript', langKey: 'typescript', icon: '🟦', commentChar: '//', hint: 'scope: context, workspace' };
      case 'script/rust': case 'rust':
        return { name: 'Rust', langKey: 'rust', icon: '🦀', commentChar: '//', hint: 'scope: context, workspace' };
      case 'script/r': case 'r':
        return { name: 'R', langKey: 'r', icon: '📊', commentChar: '#', hint: 'scope: context, workspace' };
      case 'script/octave': case 'octave':
        return { name: 'Octave', langKey: 'matlab', icon: '📐', commentChar: '%', hint: 'scope: context, workspace' };
      case 'script/wolfram': case 'wolfram':
        return { name: 'Wolfram', langKey: 'wolfram', icon: '🧠', commentChar: '(*', hint: 'scope: context, workspace' };
      case 'script/sage': case 'sage': case 'sagemath':
        return { name: 'SageMath', langKey: 'python', icon: '🌿', commentChar: '#', hint: 'scope: sage.all, numpy, context, workspace' };
      case 'script/maxima': case 'maxima':
        return { name: 'Maxima', langKey: 'maxima', icon: '🧮', commentChar: '/*', hint: 'scope: CAS symbols, matrices, context, workspace' };
      case 'script/powershell': case 'script/pwsh': case 'powershell': case 'pwsh':
        return { name: 'PowerShell', langKey: 'powershell', icon: '⚡', commentChar: '#', hint: 'scope: COM, .NET, context, workspace' };
      case 'script/csharp': case 'script/cs': case 'script/dotnet': case 'csharp': case 'cs': case 'dotnet':
        return { name: 'C#', langKey: 'csharp', icon: '🟣', commentChar: '//', hint: 'scope: .NET, System, context, workspace' };
      case 'script/python':
      default:
        return { name: 'Python', langKey: 'python', icon: '🐍', commentChar: '#', hint: 'scope: numpy, math, context, workspace' };
    }
  };
  const langDetails = getLanguageDetails();
  const defaultCodeForLang = getLanguageDefaultCode(actionType);

  const [currentCode, setCurrentCode] = useState(code || defaultCodeForLang);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevNodeIdRef = useRef<string | null>(null);
  const currentCodeRef = useRef(currentCode);
  currentCodeRef.current = currentCode;
  const onCodeChangeRef = useRef(onCodeChange);
  onCodeChangeRef.current = onCodeChange;
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const tsUpdateRef = useRef<((text: string) => void) | undefined>(undefined);

  // Resize Drawer Logic
  const [drawerWidth, setDrawerWidth] = useState(600);
  const isResizingRef = useRef(false);

  // Publish Block Form Logic
  const [showPublishForm, setShowPublishForm] = useState(false);
  const [publishForm, setPublishForm] = useState({
    displayName: '',
    category: 'User',
    icon: '⚙️',
    description: '',
    destination: 'global'
  });

  const isPublished = !actionType.startsWith('script/');

  useEffect(() => {
    if (registryLayout) {
      const isWorkspace = actionType.startsWith('workspace/');
      setPublishForm({
        displayName: isPublished ? registryLayout.name : '',
        category: isPublished ? registryLayout.category : 'User',
        icon: isPublished ? (registryLayout.icon || '⚙️') : '⚙️',
        description: isPublished ? (registryLayout.description || '') : '',
        destination: isWorkspace ? 'workspace' : 'global'
      });
    } else {
      setPublishForm({
        displayName: '',
        category: 'User',
        icon: '⚙️',
        description: '',
        destination: 'global'
      });
    }
  }, [registryLayout, actionType, isOpen]);

  const handleResize = useCallback((e: PointerEvent) => {
    if (!isResizingRef.current) return;
    const newWidth = window.innerWidth - e.clientX;
    // Limit resizing between 350px and 85% of screen width
    if (newWidth >= 350 && newWidth <= window.innerWidth * 0.85) {
      setDrawerWidth(newWidth);
    }
  }, []);

  const stopResize = useCallback(() => {
    isResizingRef.current = false;
    document.removeEventListener('pointermove', handleResize);
    document.removeEventListener('pointerup', stopResize);
    document.removeEventListener('pointercancel', stopResize);
  }, [handleResize]);

  const startResize = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    isResizingRef.current = true;
    document.addEventListener('pointermove', handleResize);
    document.addEventListener('pointerup', stopResize);
    document.addEventListener('pointercancel', stopResize);
  }, [handleResize, stopResize]);

  // Clean up global listeners on unmount
  useEffect(() => {
    return () => {
      document.removeEventListener('pointermove', handleResize);
      document.removeEventListener('pointerup', stopResize);
      document.removeEventListener('pointercancel', stopResize);
    };
  }, [handleResize, stopResize]);

  const validateAndParse = useCallback(async (codeToValidate: string, langKey: string) => {
    setIsValidating(true);
    try {
      const [parseRes, validateRes] = await Promise.all([
        axios.post(`${BACKEND_URL}/parse_script`, { code: codeToValidate, language: langKey }),
        axios.post(`${BACKEND_URL}/validate_script`, { code: codeToValidate, language: langKey })
      ]);

      if (validateRes.data.valid) {
        setValidationError(null);
      } else {
        setValidationError(validateRes.data.error || 'Syntax error');
      }

      return parseRes.data;
    } catch (err) {
      console.error('Failed to validate/parse script:', err);
      return null;
    } finally {
      setIsValidating(false);
    }
  }, []);

  useEffect(() => {
    if (prevNodeIdRef.current && prevNodeIdRef.current !== blockId && onCodeChangeRef.current) {
      onCodeChangeRef.current(prevNodeIdRef.current, currentCodeRef.current);
    }

    const newCode = code || defaultCodeForLang;
    setCurrentCode(newCode);
    setValidationError(null);
    validateAndParse(newCode, langDetails.langKey);

    if (langDetails.langKey === 'typescript' && tsUpdateRef.current) {
      tsUpdateRef.current(newCode);
    }

    prevNodeIdRef.current = blockId;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blockId]);

  const handleEditorChange = (value: string | undefined) => {
    const newCode = value || '';
    setCurrentCode(newCode);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(async () => {
      await validateAndParse(newCode, langDetails.langKey);
    }, 500);
  };

  const handleSave = async () => {
    const result = await validateAndParse(currentCode, langDetails.langKey);
    if (result) {
      onSave(currentCode, result.inputs || [], result.outputs || []);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="script-editor-drawer nodrag nowheel"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      style={{ width: `${drawerWidth}px` }}
    >
      <div className="script-editor-resize-handle" onPointerDown={startResize} />
      <div className="script-editor-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="script-editor-icon">{langDetails.icon}</span>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>{langDetails.name} {t('scriptEditor.title', 'Script Editor')}</h3>
            <span className="script-editor-block-id" style={{ marginTop: '2px' }}>{blockId}</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isValidating && (
            <span className="script-editor-status validating">{t('scriptEditor.validating', 'Validating...')}</span>
          )}
          {!isValidating && validationError === null && currentCode.trim() !== '' && (
            <span className="script-editor-status valid">{t('scriptEditor.valid', '✓ Valid')}</span>
          )}
          {!isValidating && validationError !== null && (
            <span className="script-editor-status error" title={validationError}>{t('scriptEditor.error', '✗ Error')}</span>
          )}
        </div>
      </div>

      <div className="script-editor-hint">
        {t('scriptEditor.hint', 'Use comment parameters to define block pins.')}
        Scope: <code>{langDetails.hint}</code>
      </div>

      <div className="script-editor-body">
        <Suspense fallback={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#60a5fa' }}>
            {t('scriptEditor.loadingEditor', 'Loading editor...')}
          </div>
        }>
          <MonacoEditor
            key={actionType}
            height="100%"
            language={langDetails.langKey}
            theme={appTheme === 'light' ? 'vs' : 'vs-dark'}
            value={currentCode}
            onChange={handleEditorChange}
            onMount={(editor, monaco) => {
              editorRef.current = editor;
              monacoRef.current = monaco;
              const handlers = handleEditorMount(editor, monaco, langDetails.langKey);
              if (handlers?.updateDeclarations) {
                tsUpdateRef.current = handlers.updateDeclarations;
              } else {
                tsUpdateRef.current = undefined;
              }
            }}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 4,
              insertSpaces: true,
              wordWrap: 'on',
              padding: { top: 8 },
              renderLineHighlight: 'all',
              suggestOnTriggerCharacters: true,
              quickSuggestions: true,
            }}
          />
        </Suspense>
      </div>

      <div className="script-editor-footer">
        <button className="button-secondary" onClick={onClose} style={{ flex: 1 }}>
          {t('common.cancel', 'Cancel')}
        </button>
        <button className="button-primary" onClick={handleSave} style={{ flex: 1.5 }}>
          💾 {t('scriptEditor.saveScript', 'Apply & Close')}
        </button>
        {!isPublished ? (
          <button 
            className="button-primary" 
            onClick={() => setShowPublishForm(true)} 
            style={{ flex: 1.5, background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
          >
            {t('scriptEditor.publishBlockBtn', '🚀 Publish Block')}
          </button>
        ) : (
          <button 
            className="button-primary" 
            onClick={() => setShowPublishForm(true)} 
            style={{ flex: 1.5, background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
          >
            {t('scriptEditor.updatePublished', '💾 Update Published Block')}
          </button>
        )}
      </div>

      {showPublishForm && createPortal(
        <div className="modal-overlay" style={{ zIndex: 1000 }} onClick={() => setShowPublishForm(false)}>
          <div className="modal-content glass-panel" style={{ width: '450px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0 }}>
                {isPublished ? t('scriptEditor.updatePublished', '💾 Update Published Block') : t('scriptEditor.publishAsCustom', '🚀 Publish as Custom Block')}
              </h3>
              <button className="modal-close-btn" onClick={() => setShowPublishForm(false)}>✕</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px 20px' }}>
              
              <div className="input-group">
                <label>{t('scriptEditor.blockDisplayName', 'Block Display Name')}</label>
                <input
                  type="text"
                  placeholder={t('scriptEditor.namePlaceholder', 'e.g. Waveform Generator')}
                  value={publishForm.displayName}
                  onChange={(e) => setPublishForm({ ...publishForm, displayName: e.target.value })}
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '8px', borderRadius: '6px' }}
                  disabled={isPublished} // Display name (and type/filename) are immutable for existing blocks to avoid refactoring instances
                />
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <div className="input-group" style={{ flex: 1 }}>
                  <label>{t('scriptEditor.iconLabel', 'Icon (Emoji)')}</label>
                  <input
                    type="text"
                    value={publishForm.icon}
                    onChange={(e) => setPublishForm({ ...publishForm, icon: e.target.value })}
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '8px', borderRadius: '6px', textAlign: 'center' }}
                  />
                </div>
                <div className="input-group" style={{ flex: 2 }}>
                  <label>{t('scriptEditor.category', 'Category')}</label>
                  <input
                    type="text"
                    placeholder={t('scriptEditor.categoryPlaceholder', 'User or VISA/Signal Generator')}
                    value={publishForm.category}
                    onChange={(e) => setPublishForm({ ...publishForm, category: e.target.value })}
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '8px', borderRadius: '6px' }}
                  />
                </div>
              </div>

              <div className="input-group">
                <label>{t('scriptEditor.description', 'Description')}</label>
                <textarea
                  placeholder={t('scriptEditor.descPlaceholder', 'What does this custom block do?')}
                  value={publishForm.description}
                  onChange={(e) => setPublishForm({ ...publishForm, description: e.target.value })}
                  rows={3}
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '8px', borderRadius: '6px', resize: 'vertical', fontFamily: 'inherit', fontSize: '0.85rem' }}
                />
              </div>

              <div className="input-group">
                <label>{t('scriptEditor.publishDestination', 'Publish Destination')}</label>
                <select
                  value={publishForm.destination}
                  onChange={(e) => setPublishForm({ ...publishForm, destination: e.target.value })}
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '8px', borderRadius: '6px' }}
                  disabled={isPublished} // Destination directory is fixed once published
                >
                  <option value="global">{t('scriptEditor.globalUserLibrary', 'Global User Library (~/.comfylab/user_nodes)')}</option>
                  {hasActiveWorkspace && (
                    <option value="workspace">{t('scriptEditor.activeWorkspace', 'Active Workspace (blocks/)')}</option>
                  )}
                </select>
              </div>

              {validationError && (
                <div style={{ color: '#ef4444', fontSize: '0.8rem', padding: '6px 10px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '4px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  {t('scriptEditor.validationError', '⚠️ Validation Error:')} {validationError}
                </div>
              )}

            </div>
            <div className="modal-footer" style={{ display: 'flex', gap: '10px', padding: '12px 20px' }}>
              <button className="button-secondary" onClick={() => setShowPublishForm(false)} style={{ flex: 1 }}>
                {t('common.cancel', 'Cancel')}
              </button>
              <button 
                className="button-primary" 
                onClick={async () => {
                  if (!publishForm.displayName.trim()) {
                    setValidationError(t('scriptEditor.enterDisplayName', 'Please enter a display name for the block.'));
                    return;
                  }
                  
                  setIsValidating(true);
                  try {
                    const [parseRes, validateRes] = await Promise.all([
                      axios.post(`${BACKEND_URL}/parse_script`, { code: currentCode, language: langDetails.langKey }),
                      axios.post(`${BACKEND_URL}/validate_script`, { code: currentCode, language: langDetails.langKey })
                    ]);
                    
                    if (!validateRes.data.valid) {
                      setValidationError(validateRes.data.error || t('scriptEditor.syntaxError', 'Syntax error in script.'));
                      setIsValidating(false);
                      return;
                    }

                    const pubRes = await axios.post(`${BACKEND_URL}/blocks/publish`, {
                      display_name: publishForm.displayName.trim(),
                      category: publishForm.category.trim() || 'User',
                      icon: publishForm.icon.trim() || '⚙️',
                      description: publishForm.description.trim(),
                      code: currentCode,
                      language: langDetails.langKey,
                      inputs: parseRes.data.inputs || [],
                      outputs: parseRes.data.outputs || [],
                      destination: publishForm.destination
                    });

                    if (pubRes.data.success) {
                      setShowPublishForm(false);
                      onPublishSuccess();
                      onClose();
                    }
                  } catch (err: any) {
                    console.error('Publish failed:', err);
                    setValidationError(err.response?.data?.detail || t('scriptEditor.publishFailed', 'Failed to publish block.'));
                  } finally {
                    setIsValidating(false);
                  }
                }} 
                style={{ flex: 1.5, background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
                disabled={isValidating}
              >
                {isValidating ? t('scriptEditor.publishing', 'Publishing...') : t('scriptEditor.publish', '🚀 Publish')}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
