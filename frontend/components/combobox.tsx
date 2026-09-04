"use client";

import { CheckIcon, ChevronUpDownIcon, XMarkIcon } from "@heroicons/react/20/solid";
import React, {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

export interface ComboboxOption {
  value: string;
  label: string;
  description?: string;
}

export interface ComboboxProps {
  options: Array<ComboboxOption | string>;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  label?: string;
  className?: string;
  allowCustomValue?: boolean;
  disabled?: boolean;
  size?: "sm" | "md";
  clearable?: boolean;
  id?: string;
}

export function Combobox({
  options: rawOptions,
  value,
  onChange,
  placeholder = "Select or search…",
  searchPlaceholder = "Type to search…",
  label,
  className = "",
  allowCustomValue = false,
  disabled = false,
  size = "md",
  clearable = true,
  id: customId,
}: ComboboxProps) {
  const autoId = useId();
  const inputId = customId || autoId;
  const listboxId = `${inputId}-listbox`;

  // Normalize options to ComboboxOption objects
  const options: ComboboxOption[] = useMemo(() => {
    return rawOptions.map((opt) =>
      typeof opt === "string" ? { value: opt, label: opt } : opt
    );
  }, [rawOptions]);

  // Selected option lookup
  const selectedOption = useMemo(
    () => options.find((opt) => opt.value === value),
    [options, value]
  );

  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);

  // Sync display text when value changes from outside
  useEffect(() => {
    if (selectedOption) {
      setSearchQuery(selectedOption.label);
    } else if (value) {
      setSearchQuery(value);
    } else {
      setSearchQuery("");
    }
  }, [value, selectedOption]);

  // Filter options based on query when open
  const filteredOptions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    // If the search query exactly equals the currently selected label, show all options
    if (selectedOption && searchQuery === selectedOption.label) {
      return options;
    }
    if (!q) return options;
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(q) ||
        opt.value.toLowerCase().includes(q) ||
        (opt.description && opt.description.toLowerCase().includes(q))
    );
  }, [options, searchQuery, selectedOption]);

  // Reset highlight index when filtered list changes
  useEffect(() => {
    setHighlightedIndex(0);
  }, [filteredOptions]);

  // Keep highlighted item in view
  useEffect(() => {
    if (isOpen && listboxRef.current) {
      const activeEl = listboxRef.current.children[highlightedIndex] as HTMLElement;
      if (activeEl) {
        activeEl.scrollIntoView({ block: "nearest" });
      }
    }
  }, [highlightedIndex, isOpen]);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        // Reset query text back to selected label if custom values not allowed
        if (!allowCustomValue) {
          setSearchQuery(selectedOption ? selectedOption.label : value || "");
        } else if (searchQuery.trim() !== value) {
          onChange(searchQuery.trim());
        }
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [allowCustomValue, onChange, searchQuery, selectedOption, value]);

  const selectOption = useCallback(
    (option: ComboboxOption) => {
      onChange(option.value);
      setSearchQuery(option.label);
      setIsOpen(false);
      inputRef.current?.focus();
    },
    [onChange]
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange("");
      setSearchQuery("");
      setIsOpen(false);
      inputRef.current?.focus();
    },
    [onChange]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return;

    if (!isOpen) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter") {
        e.preventDefault();
        setIsOpen(true);
        return;
      }
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev < filteredOptions.length - 1 ? prev + 1 : 0
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev > 0 ? prev - 1 : Math.max(0, filteredOptions.length - 1)
        );
        break;
      case "Enter":
        e.preventDefault();
        if (isOpen && filteredOptions[highlightedIndex]) {
          selectOption(filteredOptions[highlightedIndex]);
        } else if (allowCustomValue && searchQuery.trim()) {
          onChange(searchQuery.trim());
          setIsOpen(false);
        }
        break;
      case "Escape":
        e.preventDefault();
        setIsOpen(false);
        setSearchQuery(selectedOption ? selectedOption.label : value || "");
        break;
      case "Tab":
        if (isOpen && filteredOptions[highlightedIndex]) {
          selectOption(filteredOptions[highlightedIndex]);
        }
        setIsOpen(false);
        break;
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const text = e.target.value;
    setSearchQuery(text);
    if (!isOpen) setIsOpen(true);
    if (allowCustomValue) {
      onChange(text);
    }
  };

  const handleInputFocus = () => {
    if (!disabled) {
      setIsOpen(true);
    }
  };

  const isSmall = size === "sm";

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      {label && (
        <label
          htmlFor={inputId}
          className="mb-1.5 block font-mono text-[10px] font-semibold uppercase tracking-wider text-[#9a9a9a]"
        >
          {label}
        </label>
      )}

      <div
        className={`relative flex items-center rounded-md border bg-[#0c0c0c] transition-colors ${
          disabled
            ? "cursor-not-allowed border-[#222222] opacity-60"
            : isOpen
            ? "border-[#ccf200] shadow-[0_0_0_1px_rgba(204,242,0,0.2)]"
            : "border-[#262626] hover:border-[#3d3d3d]"
        } ${isSmall ? "h-8 text-xs" : "h-10 text-sm"}`}
      >
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={
            isOpen && filteredOptions[highlightedIndex]
              ? `${inputId}-opt-${highlightedIndex}`
              : undefined
          }
          disabled={disabled}
          value={searchQuery}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onKeyDown={handleKeyDown}
          placeholder={isOpen ? searchPlaceholder : placeholder}
          autoComplete="off"
          className={`w-full bg-transparent font-mono text-[#ffffff] placeholder:text-[#646464] focus:outline-none ${
            isSmall ? "px-2.5 text-xs" : "px-3 text-xs"
          } ${clearable && value ? "pr-14" : "pr-8"}`}
        />

        <div className="absolute right-1.5 flex items-center gap-1">
          {clearable && value && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              className="rounded p-1 text-[#646464] hover:bg-[#161616] hover:text-[#ffffff]"
              aria-label="Clear selection"
              tabIndex={-1}
            >
              <XMarkIcon className="size-3.5" />
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              if (!disabled) {
                setIsOpen((prev) => !prev);
                inputRef.current?.focus();
              }
            }}
            className="rounded p-1 text-[#646464] hover:text-[#ffffff]"
            aria-label="Toggle options menu"
            tabIndex={-1}
          >
            <ChevronUpDownIcon className="size-4" />
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 min-w-[200px] overflow-hidden rounded-md border border-[#222222] bg-[#0c0c0c] shadow-2xl">
          <ul
            ref={listboxRef}
            id={listboxId}
            role="listbox"
            tabIndex={-1}
            className="max-h-60 overflow-y-auto p-1 font-mono text-xs focus:outline-none"
          >
            {filteredOptions.length > 0 ? (
              filteredOptions.map((opt, index) => {
                const isSelected = opt.value === value;
                const isHighlighted = index === highlightedIndex;

                return (
                  <li
                    key={opt.value || `empty-${index}`}
                    id={`${inputId}-opt-${index}`}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => selectOption(opt)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={`flex cursor-pointer items-center justify-between rounded px-3 py-2 text-left transition-colors ${
                      isHighlighted
                        ? "bg-[#161616] text-[#ccf200]"
                        : isSelected
                        ? "bg-[#141414] text-[#ffffff]"
                        : "text-[#9a9a9a] hover:bg-[#141414]"
                    }`}
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <div className="truncate font-medium">{opt.label}</div>
                      {opt.description && (
                        <div className="truncate text-[10px] text-[#646464]">
                          {opt.description}
                        </div>
                      )}
                    </div>
                    {isSelected && (
                      <CheckIcon className="size-4 shrink-0 text-[#ccf200]" />
                    )}
                  </li>
                );
              })
            ) : (
              <li className="px-3 py-4 text-center text-[11px] text-[#646464]">
                {allowCustomValue ? (
                  <span>
                    Press Enter to use &ldquo;{searchQuery.trim()}&rdquo;
                  </span>
                ) : (
                  <span>No matching options</span>
                )}
              </li>
            )}
          </ul>

          {allowCustomValue && searchQuery.trim() && (
            <div className="border-t border-[#222222] bg-[#090909] px-3 py-1.5 font-mono text-[10px] text-[#646464]">
              Direct entry enabled: Enter to submit
            </div>
          )}
        </div>
      )}
    </div>
  );
}
