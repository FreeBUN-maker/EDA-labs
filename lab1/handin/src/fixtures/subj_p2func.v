// HW1 subject: the Problem-2(b) function.
// f = (a&d) | (b&c&d) | (a&c)
module p2func(a, b, c, d, f);
  input a, b, c, d;
  output f;
  assign f = (a & d) | (b & c & d) | (a & c);
endmodule
