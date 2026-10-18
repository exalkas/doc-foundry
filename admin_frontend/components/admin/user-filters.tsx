"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface UserFiltersProps {
  roleFilter: string;
  onRoleChange: (role: string) => void;
}

export function UserFilters({ roleFilter, onRoleChange }: UserFiltersProps) {
  return (
    <Select value={roleFilter} onValueChange={onRoleChange}>
      <SelectTrigger className="w-full sm:w-[180px]">
        <SelectValue placeholder="Filter by role" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All Roles</SelectItem>
        <SelectItem value="admin">Admin</SelectItem>
        <SelectItem value="owner">Owner</SelectItem>
        <SelectItem value="member">Member</SelectItem>
        <SelectItem value="readonly">Readonly</SelectItem>
      </SelectContent>
    </Select>
  );
}
