import Lake
open Lake DSL

package «aopl_formal» where
  moreLeanArgs := #[]

lean_lib «AoplFormal» where

@[default_target]
lean_exe "aopl_formal_main" where
  root := `Main
