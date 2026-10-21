import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { docsSchema } from '@davidebisio/site-kit/content';

// The docs are the plugin's own Markdown, published where it lives so it never drifts:
// workflow/README.md becomes /docs/workflow/ and each workflow/skills/<name>/SKILL.md
// becomes /docs/skills/<name>/. Sidebar titles, groups and order are set in src/lib/docs.ts.
export const collections = {
  docs: defineCollection({
    loader: glob({
      base: '../workflow',
      pattern: ['README.md', 'skills/*/SKILL.md'],
      generateId: ({ entry }) => (entry === 'README.md' ? 'workflow' : entry.replace(/\/SKILL\.md$/, '')),
    }),
    // SKILL.md frontmatter carries `name` (and keys only Claude Code reads, which are dropped).
    schema: docsSchema.extend({ name: z.string().optional() }),
  }),
};
