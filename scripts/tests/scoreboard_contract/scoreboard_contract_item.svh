class scoreboard_contract_item extends uvmf_transaction_base;
  int unsigned payload;

  `uvm_object_utils(scoreboard_contract_item)

  // Explicit constructors keep the fixture independent of dv_macros.svh.
  function new(string name = "");
    super.new(name);
  endfunction : new

  static function scoreboard_contract_item make(int unsigned key, int unsigned payload);
    scoreboard_contract_item item;
    item = scoreboard_contract_item::type_id::create("item");
    item.key = key;
    item.payload = payload;
    return item;
  endfunction : make

  virtual function bit do_compare(uvm_object rhs, uvm_comparer comparer);
    scoreboard_contract_item other;
    if (!$cast(other, rhs)) begin
      return 0;
    end
    return super.do_compare(rhs, comparer) && (key == other.key) && (payload == other.payload);
  endfunction : do_compare

  virtual function string convert2string();
    return $sformatf("key=%0d payload=%0d", key, payload);
  endfunction : convert2string
endclass : scoreboard_contract_item
