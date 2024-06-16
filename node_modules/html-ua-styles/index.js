export default [
  {
    type: 'Styles',
    selectors: [
      'area',
      'base',
      'basefont',
      'datalist',
      'head',
      'link',
      'meta',
      'noembed',
      'noframes',
      'param',
      'rp',
      'script',
      'style',
      'template',
      'title',
    ],
    styles: [
      {
        property: 'display',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['[hidden]:not([hidden="until-found" i]):not(embed)'],
    styles: [
      {
        property: 'display',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['[hidden="until-found" i]:not(embed)'],
    styles: [
      {
        property: 'content-visibility',
        value: 'hidden',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['embed[hidden]'],
    styles: [
      {
        property: 'display',
        value: 'inline',
      },
      {
        property: 'height',
        value: '0',
      },
      {
        property: 'width',
        value: '0',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['input[type="hidden" i]'],
    styles: [
      {
        property: 'display',
        value: 'none',
      },
    ],
  },
  {
    type: 'MediaQuery',
    value: '(scripting)',
    rules: [
      {
        type: 'Styles',
        selectors: ['noscript'],
        styles: [
          {
            property: 'display',
            value: 'none',
          },
        ],
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['html', 'body'],
    styles: [
      {
        property: 'display',
        value: 'block',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'address',
      'blockquote',
      'center',
      'dialog',
      'div',
      'figure',
      'figcaption',
      'footer',
      'form',
      'header',
      'hr',
      'legend',
      'listing',
      'main',
      'p',
      'plaintext',
      'pre',
      'search',
      'xmp',
    ],
    styles: [
      {
        property: 'display',
        value: 'block',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'blockquote',
      'figure',
      'listing',
      'p',
      'plaintext',
      'pre',
      'xmp',
    ],
    styles: [
      {
        property: 'margin-block-start',
        value: '1em',
      },
      {
        property: 'margin-block-end',
        value: '1em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['blockquote', 'figure'],
    styles: [
      {
        property: 'margin-inline-start',
        value: '40px',
      },
      {
        property: 'margin-inline-end',
        value: '40px',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['address'],
    styles: [
      {
        property: 'font-style',
        value: 'italic',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['listing', 'plaintext', 'pre', 'xmp'],
    styles: [
      {
        property: 'font-family',
        value: 'monospace',
      },
      {
        property: 'white-space',
        value: 'pre',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dialog:not([open])'],
    styles: [
      {
        property: 'display',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dialog'],
    styles: [
      {
        property: 'position',
        value: 'absolute',
      },
      {
        property: 'inset-inline-start',
        value: '0',
      },
      {
        property: 'inset-inline-end',
        value: '0',
      },
      {
        property: 'width',
        value: 'fit-content',
      },
      {
        property: 'height',
        value: 'fit-content',
      },
      {
        property: 'margin',
        value: 'auto',
      },
      {
        property: 'border',
        value: 'solid',
      },
      {
        property: 'padding',
        value: '1em',
      },
      {
        property: 'background-color',
        value: 'Canvas',
      },
      {
        property: 'color',
        value: 'CanvasText',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dialog:modal'],
    styles: [
      {
        property: 'position',
        value: 'fixed',
      },
      {
        property: 'overflow',
        value: 'auto',
      },
      {
        property: 'inset-block',
        value: '0',
      },
      {
        property: 'max-width',
        value: 'calc(100% - 6px - 2em)',
      },
      {
        property: 'max-height',
        value: 'calc(100% - 6px - 2em)',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dialog::backdrop'],
    styles: [
      {
        property: 'background',
        value: 'rgba(0,0,0,0.1)',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['[popover]:not(:popover-open):not(dialog[open])'],
    styles: [
      {
        property: 'display',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dialog:popover-open'],
    styles: [
      {
        property: 'display',
        value: 'block',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['[popover]'],
    styles: [
      {
        property: 'position',
        value: 'fixed',
      },
      {
        property: 'inset',
        value: '0',
      },
      {
        property: 'width',
        value: 'fit-content',
      },
      {
        property: 'height',
        value: 'fit-content',
      },
      {
        property: 'margin',
        value: 'auto',
      },
      {
        property: 'border',
        value: 'solid',
      },
      {
        property: 'padding',
        value: '0.25em',
      },
      {
        property: 'overflow',
        value: 'auto',
      },
      {
        property: 'color',
        value: 'CanvasText',
      },
      {
        property: 'background-color',
        value: 'Canvas',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':popover-open::backdrop'],
    styles: [
      {
        property: 'position',
        value: 'fixed',
      },
      {
        property: 'inset',
        value: '0',
      },
      {
        property: 'pointer-events',
        value: 'none',
      },
      {
        property: 'background-color',
        value: 'transparent',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['slot'],
    styles: [
      {
        property: 'display',
        value: 'contents',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['pre[wrap]'],
    styles: [
      {
        property: 'white-space',
        value: 'pre-wrap',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['form'],
    styles: [
      {
        property: 'margin-block-end',
        value: '1em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['cite', 'dfn', 'em', 'i', 'var'],
    styles: [
      {
        property: 'font-style',
        value: 'italic',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['b', 'strong'],
    styles: [
      {
        property: 'font-weight',
        value: 'bolder',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['code', 'kbd', 'samp', 'tt'],
    styles: [
      {
        property: 'font-family',
        value: 'monospace',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['big'],
    styles: [
      {
        property: 'font-size',
        value: 'larger',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['small'],
    styles: [
      {
        property: 'font-size',
        value: 'smaller',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['sub'],
    styles: [
      {
        property: 'vertical-align',
        value: 'sub',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['sup'],
    styles: [
      {
        property: 'vertical-align',
        value: 'super',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['sub', 'sup'],
    styles: [
      {
        property: 'line-height',
        value: 'normal',
      },
      {
        property: 'font-size',
        value: 'smaller',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ruby'],
    styles: [
      {
        property: 'display',
        value: 'ruby',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['rt'],
    styles: [
      {
        property: 'display',
        value: 'ruby-text',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':link'],
    styles: [
      {
        property: 'color',
        value: '#0000EE',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':visited'],
    styles: [
      {
        property: 'color',
        value: '#551A8B',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':link:active', ':visited:active'],
    styles: [
      {
        property: 'color',
        value: '#FF0000',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':link', ':visited'],
    styles: [
      {
        property: 'text-decoration',
        value: 'underline',
      },
      {
        property: 'cursor',
        value: 'pointer',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':focus-visible'],
    styles: [
      {
        property: 'outline',
        value: 'auto',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['mark'],
    styles: [
      {
        property: 'background',
        value: 'yellow',
      },
      {
        property: 'color',
        value: 'black',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['abbr[title]', 'acronym[title]'],
    styles: [
      {
        property: 'text-decoration',
        value: 'dotted underline',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ins', 'u'],
    styles: [
      {
        property: 'text-decoration',
        value: 'underline',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['del', 's', 'strike'],
    styles: [
      {
        property: 'text-decoration',
        value: 'line-through',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['q::before'],
    styles: [
      {
        property: 'content',
        value: 'open-quote',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['q::after'],
    styles: [
      {
        property: 'content',
        value: 'close-quote',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['br'],
    styles: [
      {
        property: 'display-outside',
        value: 'newline',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['nobr'],
    styles: [
      {
        property: 'white-space',
        value: 'nowrap',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['wbr'],
    styles: [
      {
        property: 'display-outside',
        value: 'break-opportunity',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['nobr wbr'],
    styles: [
      {
        property: 'white-space',
        value: 'normal',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['br[clear="left" i]'],
    styles: [
      {
        property: 'clear',
        value: 'left',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['br[clear="right" i]'],
    styles: [
      {
        property: 'clear',
        value: 'right',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['br[clear="all" i]', 'br[clear="both" i]'],
    styles: [
      {
        property: 'clear',
        value: 'both',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      '[dir]:dir(ltr)',
      'bdi:dir(ltr)',
      'input[type="tel" i]:dir(ltr)',
    ],
    styles: [
      {
        property: 'direction',
        value: 'ltr',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['[dir]:dir(rtl)', 'bdi:dir(rtl)'],
    styles: [
      {
        property: 'direction',
        value: 'rtl',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'address',
      'blockquote',
      'center',
      'div',
      'figure',
      'figcaption',
      'footer',
      'form',
      'header',
      'hr',
      'legend',
      'listing',
      'main',
      'p',
      'plaintext',
      'pre',
      'summary',
      'xmp',
      'article',
      'aside',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'hgroup',
      'nav',
      'section',
      'search',
      'table',
      'caption',
      'colgroup',
      'col',
      'thead',
      'tbody',
      'tfoot',
      'tr',
      'td',
      'th',
      'dir',
      'dd',
      'dl',
      'dt',
      'menu',
      'ol',
      'ul',
      'li',
      'bdi',
      'output',
      '[dir="ltr" i]',
      '[dir="rtl" i]',
      '[dir="auto" i]',
    ],
    styles: [
      {
        property: 'unicode-bidi',
        value: 'isolate',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['bdo', 'bdo[dir]'],
    styles: [
      {
        property: 'unicode-bidi',
        value: 'isolate-override',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'input[dir="auto" i]:is([type="search" i], [type="tel" i], [type="url" i], [type="email" i])',
      'textarea[dir="auto" i]',
      'pre[dir="auto" i]',
    ],
    styles: [
      {
        property: 'unicode-bidi',
        value: 'plaintext',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'address',
      'blockquote',
      'center',
      'div',
      'figure',
      'figcaption',
      'footer',
      'form',
      'header',
      'hr',
      'legend',
      'listing',
      'main',
      'p',
      'plaintext',
      'pre',
      'summary',
      'xmp',
      'article',
      'aside',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'hgroup',
      'nav',
      'section',
      'search',
      'table',
      'caption',
      'colgroup',
      'col',
      'thead',
      'tbody',
      'tfoot',
      'tr',
      'td',
      'th',
      'dir',
      'dd',
      'dl',
      'dt',
      'menu',
      'ol',
      'ul',
      'li',
      '[dir="ltr" i]',
      '[dir="rtl" i]',
      '[dir="auto" i]',
      '*|*',
    ],
    styles: [
      {
        property: 'unicode-bidi',
        value: 'bidi-override',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'input:not([type="submit" i]):not([type="reset" i]):not([type="button" i])',
      'textarea',
    ],
    styles: [
      {
        property: 'unicode-bidi',
        value: 'normal',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'article',
      'aside',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'hgroup',
      'nav',
      'section',
    ],
    styles: [
      {
        property: 'display',
        value: 'block',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['h1'],
    styles: [
      {
        property: 'margin-block-start',
        value: '0.67em',
      },
      {
        property: 'margin-block-end',
        value: '0.67em',
      },
      {
        property: 'font-size',
        value: '2.00em',
      },
      {
        property: 'font-weight',
        value: 'bold',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['h2'],
    styles: [
      {
        property: 'margin-block-start',
        value: '0.83em',
      },
      {
        property: 'margin-block-end',
        value: '0.83em',
      },
      {
        property: 'font-size',
        value: '1.50em',
      },
      {
        property: 'font-weight',
        value: 'bold',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['h3'],
    styles: [
      {
        property: 'margin-block-start',
        value: '1.00em',
      },
      {
        property: 'margin-block-end',
        value: '1.00em',
      },
      {
        property: 'font-size',
        value: '1.17em',
      },
      {
        property: 'font-weight',
        value: 'bold',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['h4'],
    styles: [
      {
        property: 'margin-block-start',
        value: '1.33em',
      },
      {
        property: 'margin-block-end',
        value: '1.33em',
      },
      {
        property: 'font-size',
        value: '1.00em',
      },
      {
        property: 'font-weight',
        value: 'bold',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['h5'],
    styles: [
      {
        property: 'margin-block-start',
        value: '1.67em',
      },
      {
        property: 'margin-block-end',
        value: '1.67em',
      },
      {
        property: 'font-size',
        value: '0.83em',
      },
      {
        property: 'font-weight',
        value: 'bold',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['h6'],
    styles: [
      {
        property: 'margin-block-start',
        value: '2.33em',
      },
      {
        property: 'margin-block-end',
        value: '2.33em',
      },
      {
        property: 'font-size',
        value: '0.67em',
      },
      {
        property: 'font-weight',
        value: 'bold',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['x h1'],
    styles: [
      {
        property: 'margin-block-start',
        value: '0.83em',
      },
      {
        property: 'margin-block-end',
        value: '0.83em',
      },
      {
        property: 'font-size',
        value: '1.50em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['x x h1'],
    styles: [
      {
        property: 'margin-block-start',
        value: '1.00em',
      },
      {
        property: 'margin-block-end',
        value: '1.00em',
      },
      {
        property: 'font-size',
        value: '1.17em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['x x x h1'],
    styles: [
      {
        property: 'margin-block-start',
        value: '1.33em',
      },
      {
        property: 'margin-block-end',
        value: '1.33em',
      },
      {
        property: 'font-size',
        value: '1.00em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['x x x x h1'],
    styles: [
      {
        property: 'margin-block-start',
        value: '1.67em',
      },
      {
        property: 'margin-block-end',
        value: '1.67em',
      },
      {
        property: 'font-size',
        value: '0.83em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['x x x x x h1'],
    styles: [
      {
        property: 'margin-block-start',
        value: '2.33em',
      },
      {
        property: 'margin-block-end',
        value: '2.33em',
      },
      {
        property: 'font-size',
        value: '0.67em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dir', 'dd', 'dl', 'dt', 'menu', 'ol', 'ul'],
    styles: [
      {
        property: 'display',
        value: 'block',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['li'],
    styles: [
      {
        property: 'display',
        value: 'list-item',
      },
      {
        property: 'text-align',
        value: 'match-parent',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dir', 'dl', 'menu', 'ol', 'ul'],
    styles: [
      {
        property: 'margin-block-start',
        value: '1em',
      },
      {
        property: 'margin-block-end',
        value: '1em',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':is(dir, dl, menu, ol, ul) :is(dir, dl, menu, ol, ul)'],
    styles: [
      {
        property: 'margin-block-start',
        value: '0',
      },
      {
        property: 'margin-block-end',
        value: '0',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dd'],
    styles: [
      {
        property: 'margin-inline-start',
        value: '40px',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dir', 'menu', 'ol', 'ul'],
    styles: [
      {
        property: 'padding-inline-start',
        value: '40px',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ol', 'ul', 'menu'],
    styles: [
      {
        property: 'counter-reset',
        value: 'list-item',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ol'],
    styles: [
      {
        property: 'list-style-type',
        value: 'decimal',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['dir', 'menu', 'ul'],
    styles: [
      {
        property: 'list-style-type',
        value: 'disc',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':is(dir, menu, ol, ul) :is(dir, menu, ul)'],
    styles: [
      {
        property: 'list-style-type',
        value: 'circle',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      ':is(dir, menu, ol, ul) :is(dir, menu, ol, ul) :is(dir, menu, ul)',
    ],
    styles: [
      {
        property: 'list-style-type',
        value: 'square',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ol[type="1"]', 'li[type="1"]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'decimal',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ol[type="a" s]', 'li[type="a" s]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'lower-alpha',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ol[type="A" s]', 'li[type="A" s]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'upper-alpha',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ol[type="i" s]', 'li[type="i" s]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'lower-roman',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ol[type="I" s]', 'li[type="I" s]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'upper-roman',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ul[type="none" i]', 'li[type="none" i]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ul[type="disc" i]', 'li[type="disc" i]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'disc',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ul[type="circle" i]', 'li[type="circle" i]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'circle',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['ul[type="square" i]', 'li[type="square" i]'],
    styles: [
      {
        property: 'list-style-type',
        value: 'square',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table'],
    styles: [
      {
        property: 'display',
        value: 'table',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['caption'],
    styles: [
      {
        property: 'display',
        value: 'table-caption',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['colgroup', 'colgroup[hidden]'],
    styles: [
      {
        property: 'display',
        value: 'table-column-group',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['col', 'col[hidden]'],
    styles: [
      {
        property: 'display',
        value: 'table-column',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['thead', 'thead[hidden]'],
    styles: [
      {
        property: 'display',
        value: 'table-header-group',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['tbody', 'tbody[hidden]'],
    styles: [
      {
        property: 'display',
        value: 'table-row-group',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['tfoot', 'tfoot[hidden]'],
    styles: [
      {
        property: 'display',
        value: 'table-footer-group',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['tr', 'tr[hidden]'],
    styles: [
      {
        property: 'display',
        value: 'table-row',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['td', 'th'],
    styles: [
      {
        property: 'display',
        value: 'table-cell',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'colgroup[hidden]',
      'col[hidden]',
      'thead[hidden]',
      'tbody[hidden]',
      'tfoot[hidden]',
      'tr[hidden]',
    ],
    styles: [
      {
        property: 'visibility',
        value: 'collapse',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table'],
    styles: [
      {
        property: 'box-sizing',
        value: 'border-box',
      },
      {
        property: 'border-spacing',
        value: '2px',
      },
      {
        property: 'border-collapse',
        value: 'separate',
      },
      {
        property: 'text-indent',
        value: 'initial',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['td', 'th'],
    styles: [
      {
        property: 'padding',
        value: '1px',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['th'],
    styles: [
      {
        property: 'font-weight',
        value: 'bold',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['caption'],
    styles: [
      {
        property: 'text-align',
        value: 'center',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['thead', 'tbody', 'tfoot', 'table > tr'],
    styles: [
      {
        property: 'vertical-align',
        value: 'middle',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['tr', 'td', 'th'],
    styles: [
      {
        property: 'vertical-align',
        value: 'inherit',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['thead', 'tbody', 'tfoot', 'tr'],
    styles: [
      {
        property: 'border-color',
        value: 'inherit',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[rules="none" i]',
      'table[rules="groups" i]',
      'table[rules="rows" i]',
      'table[rules="cols" i]',
      'table[rules="all" i]',
      'table[frame="void" i]',
      'table[frame="above" i]',
      'table[frame="below" i]',
      'table[frame="hsides" i]',
      'table[frame="lhs" i]',
      'table[frame="rhs" i]',
      'table[frame="vsides" i]',
      'table[frame="box" i]',
      'table[frame="border" i]',
      'table[rules="none" i] > tr > td',
      'table[rules="none" i] > tr > th',
      'table[rules="groups" i] > tr > td',
      'table[rules="groups" i] > tr > th',
      'table[rules="rows" i] > tr > td',
      'table[rules="rows" i] > tr > th',
      'table[rules="cols" i] > tr > td',
      'table[rules="cols" i] > tr > th',
      'table[rules="all" i] > tr > td',
      'table[rules="all" i] > tr > th',
      'table[rules="none" i] > thead > tr > td',
      'table[rules="none" i] > thead > tr > th',
      'table[rules="groups" i] > thead > tr > td',
      'table[rules="groups" i] > thead > tr > th',
      'table[rules="rows" i] > thead > tr > td',
      'table[rules="rows" i] > thead > tr > th',
      'table[rules="cols" i] > thead > tr > td',
      'table[rules="cols" i] > thead > tr > th',
      'table[rules="all" i] > thead > tr > td',
      'table[rules="all" i] > thead > tr > th',
      'table[rules="none" i] > tbody > tr > td',
      'table[rules="none" i] > tbody > tr > th',
      'table[rules="groups" i] > tbody > tr > td',
      'table[rules="groups" i] > tbody > tr > th',
      'table[rules="rows" i] > tbody > tr > td',
      'table[rules="rows" i] > tbody > tr > th',
      'table[rules="cols" i] > tbody > tr > td',
      'table[rules="cols" i] > tbody > tr > th',
      'table[rules="all" i] > tbody > tr > td',
      'table[rules="all" i] > tbody > tr > th',
      'table[rules="none" i] > tfoot > tr > td',
      'table[rules="none" i] > tfoot > tr > th',
      'table[rules="groups" i] > tfoot > tr > td',
      'table[rules="groups" i] > tfoot > tr > th',
      'table[rules="rows" i] > tfoot > tr > td',
      'table[rules="rows" i] > tfoot > tr > th',
      'table[rules="cols" i] > tfoot > tr > td',
      'table[rules="cols" i] > tfoot > tr > th',
      'table[rules="all" i] > tfoot > tr > td',
      'table[rules="all" i] > tfoot > tr > th',
    ],
    styles: [
      {
        property: 'border-color',
        value: 'black',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[align="left" i]'],
    styles: [
      {
        property: 'float',
        value: 'left',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[align="right" i]'],
    styles: [
      {
        property: 'float',
        value: 'right',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[align="center" i]'],
    styles: [
      {
        property: 'margin-inline-start',
        value: 'auto',
      },
      {
        property: 'margin-inline-end',
        value: 'auto',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'thead[align="absmiddle" i]',
      'tbody[align="absmiddle" i]',
      'tfoot[align="absmiddle" i]',
      'tr[align="absmiddle" i]',
      'td[align="absmiddle" i]',
      'th[align="absmiddle" i]',
    ],
    styles: [
      {
        property: 'text-align',
        value: 'center',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['caption[align="bottom" i]'],
    styles: [
      {
        property: 'caption-side',
        value: 'bottom',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'p[align="left" i]',
      'h1[align="left" i]',
      'h2[align="left" i]',
      'h3[align="left" i]',
      'h4[align="left" i]',
      'h5[align="left" i]',
      'h6[align="left" i]',
    ],
    styles: [
      {
        property: 'text-align',
        value: 'left',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'p[align="right" i]',
      'h1[align="right" i]',
      'h2[align="right" i]',
      'h3[align="right" i]',
      'h4[align="right" i]',
      'h5[align="right" i]',
      'h6[align="right" i]',
    ],
    styles: [
      {
        property: 'text-align',
        value: 'right',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'p[align="center" i]',
      'h1[align="center" i]',
      'h2[align="center" i]',
      'h3[align="center" i]',
      'h4[align="center" i]',
      'h5[align="center" i]',
      'h6[align="center" i]',
    ],
    styles: [
      {
        property: 'text-align',
        value: 'center',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'p[align="justify" i]',
      'h1[align="justify" i]',
      'h2[align="justify" i]',
      'h3[align="justify" i]',
      'h4[align="justify" i]',
      'h5[align="justify" i]',
      'h6[align="justify" i]',
    ],
    styles: [
      {
        property: 'text-align',
        value: 'justify',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'thead[valign="top" i]',
      'tbody[valign="top" i]',
      'tfoot[valign="top" i]',
      'tr[valign="top" i]',
      'td[valign="top" i]',
      'th[valign="top" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'top',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'thead[valign="middle" i]',
      'tbody[valign="middle" i]',
      'tfoot[valign="middle" i]',
      'tr[valign="middle" i]',
      'td[valign="middle" i]',
      'th[valign="middle" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'middle',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'thead[valign="bottom" i]',
      'tbody[valign="bottom" i]',
      'tfoot[valign="bottom" i]',
      'tr[valign="bottom" i]',
      'td[valign="bottom" i]',
      'th[valign="bottom" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'bottom',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'thead[valign="baseline" i]',
      'tbody[valign="baseline" i]',
      'tfoot[valign="baseline" i]',
      'tr[valign="baseline" i]',
      'td[valign="baseline" i]',
      'th[valign="baseline" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'baseline',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['td[nowrap]', 'th[nowrap]'],
    styles: [
      {
        property: 'white-space',
        value: 'nowrap',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[rules="none" i]',
      'table[rules="groups" i]',
      'table[rules="rows" i]',
      'table[rules="cols" i]',
      'table[rules="all" i]',
    ],
    styles: [
      {
        property: 'border-style',
        value: 'hidden',
      },
      {
        property: 'border-collapse',
        value: 'collapse',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[border]'],
    styles: [
      {
        property: 'border-style',
        value: 'outset',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="void" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'hidden',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="above" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'outset hidden hidden hidden',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="below" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'hidden hidden outset hidden',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="hsides" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'outset hidden outset hidden',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="lhs" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'hidden hidden hidden outset',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="rhs" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'hidden outset hidden hidden',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="vsides" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'hidden outset',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[frame="box" i]', 'table[frame="border" i]'],
    styles: [
      {
        property: 'border-style',
        value: 'outset',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[border] > tr > td',
      'table[border] > tr > th',
      'table[border] > thead > tr > td',
      'table[border] > thead > tr > th',
      'table[border] > tbody > tr > td',
      'table[border] > tbody > tr > th',
      'table[border] > tfoot > tr > td',
      'table[border] > tfoot > tr > th',
    ],
    styles: [
      {
        property: 'border-width',
        value: '1px',
      },
      {
        property: 'border-style',
        value: 'inset',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[rules="none" i] > tr > td',
      'table[rules="none" i] > tr > th',
      'table[rules="none" i] > thead > tr > td',
      'table[rules="none" i] > thead > tr > th',
      'table[rules="none" i] > tbody > tr > td',
      'table[rules="none" i] > tbody > tr > th',
      'table[rules="none" i] > tfoot > tr > td',
      'table[rules="none" i] > tfoot > tr > th',
      'table[rules="groups" i] > tr > td',
      'table[rules="groups" i] > tr > th',
      'table[rules="groups" i] > thead > tr > td',
      'table[rules="groups" i] > thead > tr > th',
      'table[rules="groups" i] > tbody > tr > td',
      'table[rules="groups" i] > tbody > tr > th',
      'table[rules="groups" i] > tfoot > tr > td',
      'table[rules="groups" i] > tfoot > tr > th',
      'table[rules="rows" i] > tr > td',
      'table[rules="rows" i] > tr > th',
      'table[rules="rows" i] > thead > tr > td',
      'table[rules="rows" i] > thead > tr > th',
      'table[rules="rows" i] > tbody > tr > td',
      'table[rules="rows" i] > tbody > tr > th',
      'table[rules="rows" i] > tfoot > tr > td',
      'table[rules="rows" i] > tfoot > tr > th',
    ],
    styles: [
      {
        property: 'border-width',
        value: '1px',
      },
      {
        property: 'border-style',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[rules="cols" i] > tr > td',
      'table[rules="cols" i] > tr > th',
      'table[rules="cols" i] > thead > tr > td',
      'table[rules="cols" i] > thead > tr > th',
      'table[rules="cols" i] > tbody > tr > td',
      'table[rules="cols" i] > tbody > tr > th',
      'table[rules="cols" i] > tfoot > tr > td',
      'table[rules="cols" i] > tfoot > tr > th',
    ],
    styles: [
      {
        property: 'border-width',
        value: '1px',
      },
      {
        property: 'border-block-start-style',
        value: 'none',
      },
      {
        property: 'border-inline-end-style',
        value: 'solid',
      },
      {
        property: 'border-block-end-style',
        value: 'none',
      },
      {
        property: 'border-inline-start-style',
        value: 'solid',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[rules="all" i] > tr > td',
      'table[rules="all" i] > tr > th',
      'table[rules="all" i] > thead > tr > td',
      'table[rules="all" i] > thead > tr > th',
      'table[rules="all" i] > tbody > tr > td',
      'table[rules="all" i] > tbody > tr > th',
      'table[rules="all" i] > tfoot > tr > td',
      'table[rules="all" i] > tfoot > tr > th',
    ],
    styles: [
      {
        property: 'border-width',
        value: '1px',
      },
      {
        property: 'border-style',
        value: 'solid',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table[rules="groups" i] > colgroup'],
    styles: [
      {
        property: 'border-inline-start-width',
        value: '1px',
      },
      {
        property: 'border-inline-start-style',
        value: 'solid',
      },
      {
        property: 'border-inline-end-width',
        value: '1px',
      },
      {
        property: 'border-inline-end-style',
        value: 'solid',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[rules="groups" i] > thead',
      'table[rules="groups" i] > tbody',
      'table[rules="groups" i] > tfoot',
    ],
    styles: [
      {
        property: 'border-block-start-width',
        value: '1px',
      },
      {
        property: 'border-block-start-style',
        value: 'solid',
      },
      {
        property: 'border-block-end-width',
        value: '1px',
      },
      {
        property: 'border-block-end-style',
        value: 'solid',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'table[rules="rows" i] > tr',
      'table[rules="rows" i] > thead > tr',
      'table[rules="rows" i] > tbody > tr',
      'table[rules="rows" i] > tfoot > tr',
    ],
    styles: [
      {
        property: 'border-block-start-width',
        value: '1px',
      },
      {
        property: 'border-block-start-style',
        value: 'solid',
      },
      {
        property: 'border-block-end-width',
        value: '1px',
      },
      {
        property: 'border-block-end-style',
        value: 'solid',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['table'],
    styles: [
      {
        property: 'font-weight',
        value: 'initial',
      },
      {
        property: 'font-style',
        value: 'initial',
      },
      {
        property: 'font-variant',
        value: 'initial',
      },
      {
        property: 'font-size',
        value: 'initial',
      },
      {
        property: 'line-height',
        value: 'initial',
      },
      {
        property: 'white-space',
        value: 'initial',
      },
      {
        property: 'text-align',
        value: 'initial',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [':is(table, thead, tbody, tfoot, tr) > form'],
    styles: [
      {
        property: 'display',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['input', 'select', 'button', 'textarea'],
    styles: [
      {
        property: 'letter-spacing',
        value: 'initial',
      },
      {
        property: 'word-spacing',
        value: 'initial',
      },
      {
        property: 'line-height',
        value: 'initial',
      },
      {
        property: 'text-transform',
        value: 'initial',
      },
      {
        property: 'text-indent',
        value: 'initial',
      },
      {
        property: 'text-shadow',
        value: 'initial',
      },
      {
        property: 'appearance',
        value: 'auto',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['input', 'select', 'textarea'],
    styles: [
      {
        property: 'text-align',
        value: 'initial',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'input:is([type="reset" i], [type="button" i], [type="submit" i])',
      'button',
    ],
    styles: [
      {
        property: 'text-align',
        value: 'center',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['input', 'button'],
    styles: [
      {
        property: 'display',
        value: 'inline-block',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'input[type="hidden" i]',
      'input[type="file" i]',
      'input[type="image" i]',
    ],
    styles: [
      {
        property: 'appearance',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'input:is([type="radio" i], [type="checkbox" i], [type="reset" i], [type="button" i], [type="submit" i], [type="color" i], [type="search" i])',
      'select',
      'button',
    ],
    styles: [
      {
        property: 'box-sizing',
        value: 'border-box',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['textarea'],
    styles: [
      {
        property: 'white-space',
        value: 'pre-wrap',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['input:not([type="image" i])', 'textarea'],
    styles: [
      {
        property: 'box-sizing',
        value: 'border-box',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['hr'],
    styles: [
      {
        property: 'color',
        value: 'gray',
      },
      {
        property: 'border-style',
        value: 'inset',
      },
      {
        property: 'border-width',
        value: '1px',
      },
      {
        property: 'margin-block-start',
        value: '0.5em',
      },
      {
        property: 'margin-inline-end',
        value: 'auto',
      },
      {
        property: 'margin-block-end',
        value: '0.5em',
      },
      {
        property: 'margin-inline-start',
        value: 'auto',
      },
      {
        property: 'overflow',
        value: 'hidden',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['hr[align="left" i]'],
    styles: [
      {
        property: 'margin-left',
        value: '0',
      },
      {
        property: 'margin-right',
        value: 'auto',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['hr[align="right" i]'],
    styles: [
      {
        property: 'margin-left',
        value: 'auto',
      },
      {
        property: 'margin-right',
        value: '0',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['hr[align="center" i]'],
    styles: [
      {
        property: 'margin-left',
        value: 'auto',
      },
      {
        property: 'margin-right',
        value: 'auto',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['hr[color]', 'hr[noshade]'],
    styles: [
      {
        property: 'border-style',
        value: 'solid',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['fieldset'],
    styles: [
      {
        property: 'display',
        value: 'block',
      },
      {
        property: 'margin-inline-start',
        value: '2px',
      },
      {
        property: 'margin-inline-end',
        value: '2px',
      },
      {
        property: 'border',
        value: 'groove 2px ThreeDFace',
      },
      {
        property: 'padding-block-start',
        value: '0.35em',
      },
      {
        property: 'padding-inline-end',
        value: '0.75em',
      },
      {
        property: 'padding-block-end',
        value: '0.625em',
      },
      {
        property: 'padding-inline-start',
        value: '0.75em',
      },
      {
        property: 'min-inline-size',
        value: 'min-content',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['legend'],
    styles: [
      {
        property: 'padding-inline-start',
        value: '2px',
      },
      {
        property: 'padding-inline-end',
        value: '2px',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['legend[align="left" i]'],
    styles: [
      {
        property: 'justify-self',
        value: 'left',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['legend[align="center" i]'],
    styles: [
      {
        property: 'justify-self',
        value: 'center',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['legend[align="right" i]'],
    styles: [
      {
        property: 'justify-self',
        value: 'right',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['iframe'],
    styles: [
      {
        property: 'border',
        value: '2px inset',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['video'],
    styles: [
      {
        property: 'object-fit',
        value: 'contain',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['img[align="left" i]'],
    styles: [
      {
        property: 'margin-right',
        value: '3px',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['img[align="right" i]'],
    styles: [
      {
        property: 'margin-left',
        value: '3px',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['iframe[frameborder="0"]', 'iframe[frameborder="no" i]'],
    styles: [
      {
        property: 'border',
        value: 'none',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'embed[align="left" i]',
      'iframe[align="left" i]',
      'img[align="left" i]',
      'input[type="image" i][align="left" i]',
      'object[align="left" i]',
    ],
    styles: [
      {
        property: 'float',
        value: 'left',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'embed[align="right" i]',
      'iframe[align="right" i]',
      'img[align="right" i]',
      'input[type="image" i][align="right" i]',
      'object[align="right" i]',
    ],
    styles: [
      {
        property: 'float',
        value: 'right',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'embed[align="top" i]',
      'iframe[align="top" i]',
      'img[align="top" i]',
      'input[type="image" i][align="top" i]',
      'object[align="top" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'top',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'embed[align="baseline" i]',
      'iframe[align="baseline" i]',
      'img[align="baseline" i]',
      'input[type="image" i][align="baseline" i]',
      'object[align="baseline" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'baseline',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'embed[align="texttop" i]',
      'iframe[align="texttop" i]',
      'img[align="texttop" i]',
      'input[type="image" i][align="texttop" i]',
      'object[align="texttop" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'text-top',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'embed[align="absmiddle" i]',
      'iframe[align="absmiddle" i]',
      'img[align="absmiddle" i]',
      'input[type="image" i][align="absmiddle" i]',
      'object[align="absmiddle" i]',
      'embed[align="abscenter" i]',
      'iframe[align="abscenter" i]',
      'img[align="abscenter" i]',
      'input[type="image" i][align="abscenter" i]',
      'object[align="abscenter" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'middle',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: [
      'embed[align="bottom" i]',
      'iframe[align="bottom" i]',
      'img[align="bottom" i]',
      'input[type="image" i][align="bottom" i]',
      'object[align="bottom" i]',
    ],
    styles: [
      {
        property: 'vertical-align',
        value: 'bottom',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['details > summary:first-of-type'],
    styles: [
      {
        property: 'display',
        value: 'list-item',
      },
      {
        property: 'counter-increment',
        value: 'list-item 0',
      },
      {
        property: 'list-style',
        value: 'disclosure-closed inside',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['details[open] > summary:first-of-type'],
    styles: [
      {
        property: 'list-style-type',
        value: 'disclosure-open',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['marquee'],
    styles: [
      {
        property: 'display',
        value: 'inline-block',
      },
      {
        property: 'text-align',
        value: 'initial',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['meter'],
    styles: [
      {
        property: 'appearance',
        value: 'auto',
      },
    ],
  },
  {
    type: 'Styles',
    selectors: ['progress'],
    styles: [
      {
        property: 'appearance',
        value: 'auto',
      },
    ],
  },
];
