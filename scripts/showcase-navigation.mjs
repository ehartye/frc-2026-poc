
export function navigation(base,current) {
  const links=[['strategy','Strategy',base+'#strategy'],['lab','Field lab',base+'field-lab.html'],
    ['roles','Alliance roles',base+'alliance-roles.html#roleLab'],['lanes','Depot lanes',base+'depot-lanes/']];
  const items=links.map(([key,title,href])=>
    '<a href="'+href+'"'+(key===current?' aria-current="page"':'')+'>'+title+'</a>').join('');
  return '<a class="skip" href="#main">Skip to content</a><header class="mast"><div class="mast-inner">'+
    '<a class="brand" href="'+base+'">2026 &nbsp;/&nbsp; ROBOT STUDY</a>'+
    '<nav aria-label="Showcase">'+items+'</nav></div></header>';
}

export function styleShowcase(html,base,current) {
  const marker='<!-- showcase-navigation -->';
  if(!html.includes(marker)) throw Error('Missing project navigation marker');
  return html.replace(marker,navigation(base,current));
}

export function styleOrbit(html) {
  if(!html.includes('<body') && html.includes('</style>') && html.includes('<main>')) {
    html=html.replace('</style>','</style></head><body class="cad-viewer">')
      .replace('A whole-robot assembly has yet to be published.', 'The current whole robot is available from Model.');
  }
  if(!html.includes('<body class="cad-viewer">') || !html.includes('<main>'))
    throw Error('The generated CAD viewer no longer exposes its page and camera landmarks');
  return html.replace('</head>','<link rel="stylesheet" href="../style.css"></head>')
    .replace('<body class="cad-viewer">','<body class="cad-viewer">'+navigation('../',''))
    .replace('<main>','<main id="main"><p class="eyebrow">2026 &nbsp;/&nbsp; Fusion orbit</p>');
}

