import { getCollection, type CollectionEntry } from 'astro:content';

// The Markdown is shared with the plugin itself, so sidebar metadata lives here instead of
// in its frontmatter. Skills are listed in the order the workflow runs them.
const SKILL_ORDER = [
  'git-dev-run',
  'git-dev-setup',
  'git-dev-target',
  'git-dev-plan',
  'git-dev-execute',
  'git-dev-review',
  'git-dev-update',
  'git-dev-new-issue',
  'git-dev-new-req',
  'git-dev-new-test',
];

type Doc = CollectionEntry<'docs'>;

function decorate(entry: Doc): Doc {
  if (entry.id === 'workflow') {
    return {
      ...entry,
      data: {
        ...entry.data,
        title: 'The workflow plugin',
        description: 'Layout, providers, agents, auto mode and the end-to-end test harness.',
        order: 0,
      },
    };
  }
  const name = entry.data.name ?? entry.id.split('/').pop()!;
  const rank = SKILL_ORDER.indexOf(name);
  return {
    ...entry,
    data: { ...entry.data, title: name, group: 'Skill reference', order: rank === -1 ? 100 : rank },
  };
}

/** Docs entries with sidebar title, group and order filled in. */
export async function getDocs(): Promise<Doc[]> {
  return (await getCollection('docs', (e) => !e.data.draft)).map(decorate);
}
