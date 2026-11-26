"use client";

import { useState } from "react";

type Option = { value: string; label: string };

export function CatalogOptionPicker({ name, label, options, selected }: { name: string; label: string; options: Option[]; selected: string[] }) {
  const [query, setQuery] = useState("");
  const [values, setValues] = useState(selected);
  const allOptions = [...options, ...selected.filter(value => !options.some(option => option.value === value)).map(value => ({ value, label: "未識別條件（保留）" }))];
  const search = query.trim().toLocaleLowerCase();
  const matches = (option: Option) => option.label.toLocaleLowerCase().includes(search) || option.value.toLocaleLowerCase().includes(search);
  return <fieldset className="catalog-option-picker">
    <legend>{label}<span>{values.length ? `已選 ${values.length} 項` : "可複選"}</span></legend>
    <div className="catalog-option-search">
      <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={`搜尋${label}`} aria-label={`搜尋${label}選項`} />
      {values.length > 0 && <button type="button" onClick={() => setValues([])} aria-label={`清除${label}選擇`}>清除</button>}
    </div>
    <div className="catalog-option-list">
      {allOptions.map(option => <label key={option.value} hidden={!matches(option)}>
        <input type="checkbox" name={name} value={option.value} checked={values.includes(option.value)} onChange={event => setValues(previous => event.target.checked ? [...previous, option.value] : previous.filter(value => value !== option.value))} />
        <span>{option.label}</span>
      </label>)}
      {!allOptions.some(matches) && <p>沒有符合的選項，已選項目仍會保留。</p>}
    </div>
  </fieldset>;
}
