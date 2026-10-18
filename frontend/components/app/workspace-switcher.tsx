"use client";

import * as React from "react";
import { Check, ChevronsUpDown, Building2, Plus } from "lucide-react";
import { useWorkspaceContext } from "@/contexts/workspace-context";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { CreateWorkspaceDialog } from "./create-workspace-dialog";

export function WorkspaceSwitcher() {
  const [open, setOpen] = React.useState(false);
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const { workspace, workspaces, switchWorkspace, loading } =
    useWorkspaceContext();

  if (loading || !workspace) {
    return (
      <Button variant="outline" disabled>
        <Building2 className="mr-2 h-4 w-4" />
        Loading...
      </Button>
    );
  }

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-[200px] justify-between"
          >
            <Building2 className="mr-2 h-4 w-4" />
            {workspace.name}
            <ChevronsUpDown className="ml-auto h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[200px] p-0">
          <Command>
            <CommandInput placeholder="Search company..." />
            <CommandList>
              <CommandEmpty>No company found.</CommandEmpty>
              <CommandGroup>
                {workspaces.map((ws) => (
                  <CommandItem
                    key={ws.id}
                    value={ws.name}
                    onSelect={() => {
                      switchWorkspace(ws.id);
                      setOpen(false);
                    }}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        workspace.id === ws.id ? "opacity-100" : "opacity-0"
                      )}
                    />
                    {ws.name}
                  </CommandItem>
                ))}
              </CommandGroup>
              <CommandSeparator />
              <CommandGroup>
                <CommandItem
                  onSelect={() => {
                    setOpen(false);
                    setCreateDialogOpen(true);
                  }}
                  className="cursor-pointer"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Create workspace
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      <CreateWorkspaceDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </>
  );
}
