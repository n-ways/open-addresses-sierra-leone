-- French typography for text that citeproc writes (the bibliography): a narrow no-break
-- space before ":", ";", "!" and "?" when they end a word. Runs after --citeproc. The
-- paper's own text already carries these spaces, so babel's automatic spacing is off and
-- identifiers such as "ISO 19160-1:2015" or "EPSG:2161" keep their colon tight.
local NNBSP = '\u{202F}'

function Pandoc(doc)
  local lang = pandoc.utils.stringify(doc.meta.lang or '')
  if not lang:match('^fr') then return nil end
  return doc:walk({
    Div = function(div)
      if div.identifier ~= 'refs' then return nil end
      return div:walk({
        Str = function(s)
          local word, mark = s.text:match('^(.-[^%s\u{202F}\u{A0}])([:;!?])$')
          if word then return pandoc.Str(word .. NNBSP .. mark) end
        end
      })
    end
  })
end
