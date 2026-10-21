-- In the PDF a figure uses its vector PDF; the markdown on the web uses the SVG.
function Image(img)
  img.src = img.src:gsub('%.svg$', '.pdf')
  return img
end

-- File paths in monospace may break after a slash, so that a long path never runs into the margin.
function Code(el)
  if FORMAT:match('latex') and el.text:find('/') then
    local tex = pandoc.write(pandoc.Pandoc({pandoc.Plain({el})}), 'latex')
    tex = tex:gsub('\n$', ''):gsub('/', '/\\allowbreak{}')
    return pandoc.RawInline('latex', tex)
  end
end

-- A short table (six rows or fewer) starts on a page with room for all of it, so that a page
-- never ends with its header or its first rows alone.
function Table(tbl)
  if not FORMAT:match('latex') then return nil end
  local rows = 0
  for _, body in ipairs(tbl.bodies) do rows = rows + #body.body end
  if rows <= 6 then
    return { pandoc.RawBlock('latex', string.format('\\needspace{%d\\baselineskip}', 2 * rows + 5)), tbl }
  end
end
