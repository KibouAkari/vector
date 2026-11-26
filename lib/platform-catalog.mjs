// Source inventory only. Never infer runtime health, permissions or provider
// availability from a card, configured URL or a model's own description.
export const PLATFORM_CAPABILITIES = [
 {id:'chat',name:'Chat and local models',status:'source',href:'/chat',detail:'Conversation and local-only paths exist. Native/provider availability still depends on the installed runtime.'},
 {id:'knowledge',name:'Projects and retained sources',status:'source',href:'/projects',detail:'Files, search and bounded public-page snapshots. Unified document ingestion and refresh/removal workflows remain incomplete.'},
 {id:'skills',name:'Project skills',status:'source',href:'/projects',detail:'Create instruction drafts, owner-review exact content, select active skills in project chat. No arbitrary skill code execution or automatic installation.'},
 {id:'work',name:'Workflows and quality review',status:'partial',href:'/projects',detail:'Sequential planner, worker and reviewer source exists. Parallel specialist teams, independent role models and shared hard call reservations remain planned.'},
 {id:'security',name:'Security evidence and reports',status:'source',href:'/security',detail:'Owner-scoped assessments, exact scope approval, imported Nmap XML and deterministic reports. This workbench does not execute scans or verify vulnerabilities.'},
 {id:'models',name:'Models, API keys and routing',status:'source',href:'/models',detail:'Encrypted provider credentials and task routing exist. Health, prices and best-model claims require measured, current evidence.'},
 {id:'cost',name:'Usage and cost control',status:'source',href:'/usage',detail:'Existing usage accounting and budget policies. No promise of one hard reservation shared by future voice, media and channel adapters.'},
 {id:'access',name:'Users and approvals',status:'source',href:'/users',detail:'Account/project access, owner-only approval decisions and policy administration.'},
 {id:'coding',name:'Coding and sandbox',status:'partial',href:'/projects',detail:'Project tools and runner client exist. Managed GitHub bot installation and turnkey client coding are not connected here.'},
 {id:'voice',name:'Live voice and calls',status:'planned',href:null,detail:'Requires a realtime transport, speech pipeline, interruption handling, call authorization and cost/recording limits.'},
 {id:'channels',name:'Mail, Discord and WhatsApp',status:'partial',href:null,detail:'The optional Minecraft/Discord bridge is independent. General-purpose mail, Discord and WhatsApp adapters and delivery guarantees remain planned.'},
 {id:'devices',name:'Windows, macOS and Linux agents',status:'planned',href:null,detail:'Requires paired device identity, scoped capabilities, revocation, updates and consent for screen/input/files. No cross-platform installer is provided yet.'},
 {id:'media',name:'Image and video studio',status:'planned',href:null,detail:'Requires provider adapters, asset provenance, previews, cancellation and per-generation spend controls.'},
 {id:'mcp',name:'MCP and workflow connectors',status:'planned',href:null,detail:'Native tool execution exists. A general MCP connection lifecycle and n8n integration are not implemented by this catalog.'},
 {id:'memory',name:'Inspectable long-term memory',status:'partial',href:'/projects',detail:'Persistent conversations and project retrieval exist. A distinct memory lifecycle with provenance, correction and expiry remains planned.'}
];
