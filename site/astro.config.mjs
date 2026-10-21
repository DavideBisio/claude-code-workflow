// @ts-check
import { defineConfig } from 'astro/config';
import siteKit from '@davidebisio/site-kit/integration';

export default defineConfig({
  site: 'https://davidebisio.github.io',
  // Project sites are served from /<repo>/. The hub (davidebisio.github.io) uses '/'.
  base: '/claude-code-workflow',
  integrations: [
    siteKit({
      title: 'claude-code-workflow',
      description: 'Gated, test-first Claude Code workflows with requirement-to-test traceability on plain GitHub issues.',
      repo: 'https://github.com/DavideBisio/claude-code-workflow',
      nav: [
        { label: 'Overview', href: '/' },
        { label: 'Docs', href: '/docs/' },
      ],
      // Opt-in, off by default: analytics: { goatcounter: 'davidebisio' },
    }),
  ],
});
