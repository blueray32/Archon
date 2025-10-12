import type React from 'react';

declare module 'prismjs';

declare namespace JSX {
  interface IntrinsicElements {
    'openai-chatkit': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        'session-endpoint'?: string;
        'workflow-id'?: string;
        theme?: string;
        uploads?: string;
      },
      HTMLElement
    >;
  }
}
