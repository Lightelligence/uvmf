#include "dpiheader.h"
#include "dpi_link.h"

// The simulator-generated header owns the ABI. In particular, supported tools
// expose DPI tasks with different C++ return types; preserve that type and status.
// Their exported input vectors also differ in constness, so derive the argument
// type instead of redeclaring exports or casting away the header's qualifiers.
template <typename Signature>
struct DpiInput;

template <typename Result, typename Argument>
struct DpiInput<Result (*)(Argument)> {
  using type = Argument;
};

extern "C" {

  auto C_access(const char* path, svBitVecVal* bit_vec)
      -> decltype(bfm_access(bit_vec, bit_vec)) {
    svSetScope(svGetScopeFromName(path));
    return bfm_access(bit_vec, bit_vec);
  }

  auto C_response(const char* path, svBitVecVal* bit_vec)
      -> decltype(response(bit_vec, bit_vec)) {
    svSetScope(svGetScopeFromName(path));
    return response(bit_vec, bit_vec);
  }

  // Associate the calling package with its monitor BFM scope for callbacks.
  void C_initialize_monitor(const char* path) {
    dpi_link::store_svScope(path);
  }

  void C_configure(const char* path, DpiInput<decltype(&configure)>::type bit_vec) {
    svSetScope(svGetScopeFromName(path));
    configure(bit_vec);
  }

  void C_do_response_ready(const char* path, DpiInput<decltype(&do_response_ready)>::type bit_vec) {
    svSetScope(svGetScopeFromName(path));
    do_response_ready(bit_vec);
  }

  void C_start_monitoring(const char* path) {
    svSetScope(svGetScopeFromName(path));
    start_monitoring();
  }

  auto C_wait_for_reset(const char* path) -> decltype(wait_for_reset()) {
    svSetScope(svGetScopeFromName(path));
    return wait_for_reset();
  }

  auto C_wait_for_num_clocks(const char* path, DpiInput<decltype(&wait_for_num_clocks)>::type bit_vec)
      -> decltype(wait_for_num_clocks(bit_vec)) {
    svSetScope(svGetScopeFromName(path));
    return wait_for_num_clocks(bit_vec);
  }
}
