import React from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Filter } from 'lucide-react';
import { useAgentState } from '../../agents/AgentContext';

export const SourceFilterControl: React.FC<{ className?: string }> = ({ className }) => {
  const { selectedSourceFilter, setSelectedSourceFilter } = useAgentState();
  const [value, setValue] = React.useState<string>(selectedSourceFilter);

  React.useEffect(() => {
    setValue(selectedSourceFilter);
  }, [selectedSourceFilter]);

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className={
            className ??
            'px-2 py-1 rounded-md border text-xs flex items-center gap-1 bg-white/70 dark:bg-zinc-900/60 border-gray-200 dark:border-gray-700'
          }
          title={selectedSourceFilter ? `Sources: ${selectedSourceFilter}` : 'Set source filter'}
        >
          <Filter className="w-3.5 h-3.5" />
          <span>Sources</span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="start"
          sideOffset={8}
          className="z-50 w-80 rounded-lg border border-gray-200 dark:border-gray-700 bg-white/95 dark:bg-zinc-900/95 shadow-xl p-3 backdrop-blur"
        >
          <div className="space-y-2 text-sm">
            <div className="text-xs text-gray-600 dark:text-gray-300">Regex or tokens separated by |</div>
            <input
              className="w-full text-sm px-2 py-1 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-zinc-800 text-gray-800 dark:text-gray-100"
              placeholder="e.g. ai-agent-mastery|pydantic|docs"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                className="text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-zinc-800"
                onClick={() => {
                  setValue('');
                  setSelectedSourceFilter('');
                }}
              >
                Clear
              </button>
              <button
                className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
                onClick={() => setSelectedSourceFilter(value.trim())}
              >
                Save
              </button>
            </div>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
};

