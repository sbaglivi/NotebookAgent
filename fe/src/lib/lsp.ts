import * as monaco from 'monaco-editor';

class LSPManager {
    private sockets: Map<string, WebSocket> = new Map();
    private pendingRequests: Map<number, (response: any) => void> = new Map();
    private reqId = 0;
    private initialized = false;

    register(uri: string, ws: WebSocket) {
        this.sockets.set(uri, ws);
        this.initMonaco();
    }

    unregister(uri: string) {
        this.sockets.delete(uri);
    }

    handleMessage(msg: any) {
        if (msg.id !== undefined && this.pendingRequests.has(msg.id)) {
            const resolve = this.pendingRequests.get(msg.id);
            this.pendingRequests.delete(msg.id);
            if (resolve) resolve(msg);
        }
    }

    private initMonaco() {
        if (this.initialized) return;
        this.initialized = true;

        monaco.languages.registerCompletionItemProvider('python', {
            triggerCharacters: ['.'],
            provideCompletionItems: async (model, position) => {
                const uri = model.uri.toString();
                const ws = this.sockets.get(uri);
                if (!ws) return { suggestions: [] };

                const id = this.reqId++;
                const req = {
                    jsonrpc: "2.0",
                    id,
                    method: "textDocument/completion",
                    params: {
                        textDocument: { uri },
                        position: {
                            line: position.lineNumber - 1,
                            character: position.column - 1
                        }
                    }
                };

                return new Promise<any>((resolve) => {
                    this.pendingRequests.set(id, (response) => {
                        const items = response.result?.items || [];
                        resolve({
                            suggestions: items.map((item: any) => ({
                                label: item.label,
                                kind: item.kind, // Map LSP kind to Monaco kind if needed
                                insertText: item.insertText || item.label,
                                range: undefined // Let Monaco handle range?
                            }))
                        });
                    });
                    ws.send(JSON.stringify(req));
                });
            }
        });

        monaco.languages.registerHoverProvider('python', {
            provideHover: async (model, position) => {
                const uri = model.uri.toString();
                const ws = this.sockets.get(uri);
                if (!ws) return null;

                const id = this.reqId++;
                const req = {
                    jsonrpc: "2.0",
                    id,
                    method: "textDocument/hover",
                    params: {
                        textDocument: { uri },
                        position: {
                            line: position.lineNumber - 1,
                            character: position.column - 1
                        }
                    }
                };

                return new Promise<any>((resolve) => {
                    this.pendingRequests.set(id, (response) => {
                        if (!response.result || !response.result.contents) {
                            resolve(null);
                            return;
                        }
                        let contents = response.result.contents;
                        if (typeof contents === 'string') contents = [{ value: contents }];
                        else if (!Array.isArray(contents)) contents = [contents];
                        
                        resolve({
                            contents: contents.map((c: any) => ({
                                value: c.value || c
                            }))
                        });
                    });
                    ws.send(JSON.stringify(req));
                });
            }
        });
    }
}

export const lspManager = new LSPManager();
