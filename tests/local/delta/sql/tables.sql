-- SPETLR.CONFIGURATOR key: Table1
CREATE TABLE IF NOT EXISTS SomeTable(
a int
)
USING DELTA;

-- SPETLR.CONFIGURATOR key: Table2
CREATE TABLE IF NOT EXISTS AnotherTable(
a int,
b string
)
USING DELTA
LOCATION '/{MNT}/foo/bar';
